"""
Explainer render agent (Phase A).

script (shots + scene specs) → validate/repair → Kokoro voice per shot → word
timings → props.json → Remotion render (video/explainer) → automated QA →
thumbnail + SRT captions.

Returns a dict in the same spirit as VideoAgent.render(); raises if the video
fails QA, so a broken video can never reach the uploader.
"""

import json
import logging
import os
import re
import shutil
import subprocess
from collections import deque
import time
import zlib
from pathlib import Path
from typing import Dict, List, Optional

from agents.scene_schema import validate_and_repair
from agents.word_timing import align, caption_pages, make_aligner, proportional, srt
from config import config

logger = logging.getLogger(__name__)

PROGRESS_EVERY_S = 60
_PROGRESS = re.compile(r"(Rendered|Encoded|Rendering|Stitch|frames?)\b.*?\d+\s*/\s*\d+|\d+%", re.I)

FPS = 30
REPO = Path(__file__).resolve().parent.parent


def chapters_from(shots: List[Dict]) -> List[Dict]:
    """YouTube chapters from shots with a 'chapter' field. Valid only if ≥3, first at 0:00, each ≥10 s."""
    marks = [{"t": s["start"], "title": s["chapter"]} for s in shots if s.get("chapter")]
    if not marks:
        return []
    if marks[0]["t"] > 0.5:
        marks.insert(0, {"t": 0.0, "title": "Intro"})
    marks[0]["t"] = 0.0
    end = shots[-1]["start"] + shots[-1]["duration"]
    kept = []
    for i, m in enumerate(marks):
        nxt = marks[i + 1]["t"] if i + 1 < len(marks) else end
        if nxt - m["t"] >= 10 or not kept:
            kept.append(m)
    return kept if len(kept) >= 3 else []


def fmt_ts(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


class ExplainerAgent:
    def __init__(self, explainer_dir: Optional[str] = None):
        self.dir = (REPO / (explainer_dir or config.EXPLAINER_DIR)).resolve()
        self._voice = None
        self._aligner = None
        self._aligner_loaded = False

    # ── pieces ────────────────────────────────────────────────────────────────

    def voice(self):
        if self._voice is None:
            from agents.kokoro_voice import KokoroVoice
            self._voice = KokoroVoice()
        return self._voice

    def aligner(self):
        if not self._aligner_loaded:
            self._aligner = make_aligner(config.WORD_TIMINGS)
            self._aligner_loaded = True
        return self._aligner

    def build_props(self, script: Dict, public: Path) -> Dict:
        """Voice + timings → the props.json Remotion renders. Writes voice.wav into `public`."""
        from agents.kokoro_voice import concat_and_normalize

        shots_in = script["shots"]
        texts = [s["text"] for s in shots_in]
        logger.info(f"[explainer] voice: {len(texts)} lines ({config.KOKORO_VOICE})")
        paths, durs, speech, _ = self.voice().synth_shots(texts, public.parent / "shots")
        concat_and_normalize(paths, public / "voice.wav")

        # Frame-exact shot boundaries (no cumulative drift).
        bounds, acc = [0], 0.0
        for d in durs:
            acc += d
            bounds.append(round(acc * FPS))
        aligner = self.aligner()
        shots, timing_words = [], []
        for i, s in enumerate(shots_in):
            start = bounds[i] / FPS
            duration = (bounds[i + 1] - bounds[i]) / FPS
            words = s["text"].split()
            rec = aligner.words(str(paths[i]), s["text"]) if aligner else []
            times = align(words, rec, speech[i]) if rec else proportional(words, speech[i])
            shots.append({
                "start": round(start, 4), "duration": round(duration, 4), "speech": round(speech[i], 3),
                "text": s["text"], "emphasis": s.get("emphasis", []), "scene": s["scene"],
                **({"chapter": s["chapter"]} if s.get("chapter") else {}),
            })
            timing_words.append({"start": start, "duration": duration, "emphasis": s.get("emphasis", []),
                                 "words": [(w, a, b) for w, (a, b) in zip(words, times)]})
        pages = caption_pages(timing_words)

        music = None
        if config.MUSIC_ENABLED:
            tracks = sorted(Path(REPO / config.MUSIC_DIR).glob("*.mp3"))
            if tracks:
                shutil.copy(tracks[zlib.crc32(script.get("title", "").encode()) % len(tracks)], public / "music.mp3")
                music = "music.mp3"
        return {
            "shots": shots, "captions": pages, "voice": "voice.wav", "music": music, "musicVolume": 0.07,
            "channel": config.CHANNEL_NAME, "showCaptions": True, "debugChecks": False,
            "_timing_source": "whisper" if aligner else "proportional",
        }

    def _remotion(self, args: List[str], timeout: float) -> None:
        """Run the Remotion CLI, streaming its output so long renders show progress in CI logs
        (a throttled line about once a minute) instead of going silent for half an hour."""
        cmd = ["npx", "remotion", *args, "--log=info"]
        exe = os.getenv("REMOTION_BROWSER_EXECUTABLE")
        if exe:
            cmd.append(f"--browser-executable={exe}")
        tail: deque = deque(maxlen=40)
        start = last = time.time()
        proc = subprocess.Popen(cmd, cwd=self.dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)   # text mode: \r progress updates arrive as lines
        try:
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                tail.append(line)
                now = time.time()
                if now - start > timeout:
                    proc.kill()
                    raise RuntimeError(f"remotion {args[0]} timed out after {timeout:.0f}s")
                if _PROGRESS.search(line) and now - last >= PROGRESS_EVERY_S:
                    last = now
                    logger.info(f"[explainer] remotion {args[0]} ({(now - start) / 60:.1f} min): {line[:160]}")
            rc = proc.wait(timeout=max(1, timeout - (time.time() - start)))
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(f"remotion {args[0]} timed out after {timeout:.0f}s")
        if rc != 0:
            raise RuntimeError(f"remotion {args[0]} failed: {' | '.join(tail)[-1200:]}")
        logger.info(f"[explainer] remotion {args[0]} done in {(time.time() - start) / 60:.1f} min")

    def ensure_deps(self) -> None:
        if not (self.dir / "node_modules" / "remotion").exists():
            logger.info("[explainer] installing Remotion dependencies (npm ci)…")
            res = subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=self.dir, capture_output=True, text=True, timeout=900)
            if res.returncode != 0:
                raise RuntimeError("npm ci failed: " + res.stderr[-800:])

    # ── public ────────────────────────────────────────────────────────────────

    def render(self, script: Dict, out_dir: str, min_duration: Optional[float] = None) -> Dict:
        from scripts.qa_video import run_qa

        t0 = time.time()
        out = Path(out_dir).resolve()
        public = out / "public"
        public.mkdir(parents=True, exist_ok=True)
        self.ensure_deps()

        safe, repairs = validate_and_repair(script)
        if repairs:
            logger.info(f"[explainer] {len(repairs)} scene repairs (see report)")
        props = self.build_props(safe, public)
        timing_source = props.pop("_timing_source")
        total = props["shots"][-1]["start"] + props["shots"][-1]["duration"]
        props_path = out / "props.json"
        props_path.write_text(json.dumps(props, ensure_ascii=False))
        logger.info(f"[explainer] narration {total:.1f}s, {len(props['shots'])} shots, timings={timing_source}")

        video = out / "video.mp4"
        cpus = os.cpu_count() or 2
        timeout = 600 + 8 * total
        for attempt, conc in enumerate((cpus, max(1, cpus // 2))):
            try:
                logger.info(f"[explainer] rendering with Remotion (concurrency {conc})…")
                self._remotion(["render", "src/index.ts", "Explainer", str(video), f"--props={props_path}",
                                f"--public-dir={public}", f"--concurrency={conc}", "--crf=20", "--timeout=120000"], timeout)
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 1:
                    raise
                logger.warning(f"[explainer] render failed, retrying at lower concurrency: {str(e)[:300]}")

        qa = run_qa(str(video), expected=total, min_duration=min_duration)
        (out / "qa.json").write_text(json.dumps(qa, indent=2))
        for c in qa["checks"]:
            logger.info(f"[qa] {'✓' if c['ok'] else '✗'} {c['name']}: {c['detail']}")
        if not qa["passed"]:
            raise RuntimeError("video failed QA: " + ", ".join(c["name"] for c in qa["checks"] if not c["ok"]))

        thumb = out / "thumbnail.jpg"
        thumb_png = out / "thumbnail.png"
        self._remotion(["still", "src/index.ts", "Thumbnail", str(thumb_png), "--props=" + json.dumps({
            "text": safe.get("thumbnail_text") or safe.get("title", "")[:30],
            "subtext": safe.get("thumbnail_subtext", ""),
            "icon": safe.get("thumbnail_icon", "lightbulb"),
            "channel": config.CHANNEL_NAME,
        })], 300)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(thumb_png), "-q:v", "3", str(thumb)], check=True)
        thumb_png.unlink(missing_ok=True)

        (out / "captions.srt").write_text(srt(props["captions"]), encoding="utf-8")
        chapters = chapters_from(props["shots"])
        report = {
            "duration_s": round(total, 2), "shots": len(props["shots"]), "timing_source": timing_source,
            "render_seconds": round(time.time() - t0, 1), "repairs": repairs, "chapters": chapters,
            "scene_counts": _counts(s["scene"]["type"] for s in props["shots"]), "qa": qa,
        }
        (out / "render_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        logger.info(f"[explainer] ✓ {video} ({total:.0f}s) in {report['render_seconds']}s")
        shutil.rmtree(out / "shots", ignore_errors=True)
        return {"video_path": str(video), "thumbnail_path": str(thumb), "captions_path": str(out / "captions.srt"),
                "duration": total, "chapters": chapters, "report": report, "script": safe}


def _counts(items) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def description_with_chapters(description: str, chapters: List[Dict], sources: List[Dict]) -> str:
    """Append chapter timestamps and sources to the YouTube description."""
    parts = [description.strip()]
    if chapters:
        parts.append("Chapters:\n" + "\n".join(f"{fmt_ts(c['t'])} {c['title']}" for c in chapters))
    if sources:
        parts.append("Sources:\n" + "\n".join(f"- {s.get('title', '')} {s.get('url', '')}".strip() for s in sources[:8]))
    parts.append("Narration voice is AI-generated (Kokoro TTS). Visuals are animated graphics.")
    text = "\n\n".join(p for p in parts if p)
    return re.sub(r"[<>]", "", text)[:4900]


def main() -> None:
    """Render a script JSON directly (no research, no LLM, no upload):
    python -m agents.explainer_agent tests/fixtures/explainer_script.json --out outputs/explainer_test --min 0
    """
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="outputs/explainer_test")
    ap.add_argument("--min", type=float, default=None, help="minimum length in seconds (default: none)")
    a = ap.parse_args()
    script = json.loads(Path(a.script).read_text())
    res = ExplainerAgent().render(script, a.out, min_duration=a.min)
    print(json.dumps({k: v for k, v in res.items() if k not in ("script", "report")}, indent=2))


if __name__ == "__main__":
    main()
