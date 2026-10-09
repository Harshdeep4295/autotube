"""
Kids explainer render agent ("Explained Like You're 5").

script (scenes + lines) → validate/repair → voice per line → word timings → timeline
(beats keyed to lines / cue words) → pycairo frames + ffmpeg → QA (incl. 3-minute cap)
→ thumbnail + SRT captions.

Raises if the video fails QA, so a broken video never reaches the uploader.
Offline test render (no LLM, no upload):
    python -m agents.kids_agent tests/fixtures/kids_stock_market.json --out outputs/kids_test
"""

import json
import logging
import shutil
import subprocess
import time
import zlib
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from agents.kids import render as R
from agents.kids import timeline as TLB
from agents.kids.music import make_bed
from agents.kids_scene_schema import validate_and_repair, word_count
from agents.word_timing import align, caption_pages, make_aligner, proportional, srt
from config import config

logger = logging.getLogger(__name__)
REPO = Path(__file__).resolve().parent.parent


class KidsAgent:
    def __init__(self, voice=None, aligner=None):
        self._voice = voice
        self._aligner = aligner
        self._aligner_loaded = aligner is not None

    def voice(self):
        if self._voice is None:
            from agents.kids.voice import KidsVoice
            self._voice = KidsVoice()
        return self._voice

    def aligner(self):
        if not self._aligner_loaded:
            self._aligner = make_aligner(config.WORD_TIMINGS)
            self._aligner_loaded = True
        return self._aligner

    # ── audio ────────────────────────────────────────────────────────────────
    def voice_lines(self, script: Dict, work: Path):
        """Synthesize every line separately → (voiced timings, per-line sample arrays, sample rate)."""
        import soundfile as sf

        work.mkdir(parents=True, exist_ok=True)
        voiced, audio, sr = [], [], 24000
        aligner = self.aligner()
        n = 0
        for si, sc in enumerate(script["scenes"]):
            vs, aus = [], []
            for li, ln in enumerate(sc["lines"]):
                samples, sr = self.voice().synth(ln["text"])
                speech = len(samples) / sr
                words = ln["text"].split()
                rec = []
                if aligner:
                    p = work / f"line_{si:02d}_{li}.wav"
                    sf.write(p, samples, sr)
                    try:
                        rec = aligner.words(str(p), ln["text"])
                    except Exception as e:  # noqa: BLE001
                        logger.debug(f"aligner failed: {e}")
                times = align(words, rec, speech) if rec else proportional(words, speech)
                vs.append({"dur": speech, "speech": speech, "words": [(w, a, b) for w, (a, b) in zip(words, times)]})
                aus.append(samples)
                n += 1
            voiced.append(vs)
            audio.append(aus)
        logger.info(f"[kids] voiced {n} lines ({self.voice().name}), timings={'whisper' if aligner else 'proportional'}")
        return voiced, audio, sr

    @staticmethod
    def assemble_voice(audio: List[List[np.ndarray]], gaps: List[List[float]], sr: int, out_wav: Path) -> None:
        """Concatenate lines with the same gaps the timeline used, then loudness-normalize in its own pass."""
        import soundfile as sf

        parts = [np.zeros(int(TLB.LEAD_S * sr), np.float32)]
        for aus, gs in zip(audio, gaps):
            for a, g in zip(aus, gs):
                parts.append(a.astype(np.float32))
                parts.append(np.zeros(int(round(g * sr)), np.float32))
        parts.append(np.zeros(int(TLB.TAIL_S * sr), np.float32))
        raw = out_wav.with_name(out_wav.stem + "_raw.wav")
        sf.write(raw, np.concatenate(parts), sr)
        res = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                              "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", str(out_wav)],
                             capture_output=True, timeout=600)
        if res.returncode != 0:
            raise RuntimeError("loudnorm failed: " + res.stderr.decode()[-400:])
        raw.unlink(missing_ok=True)

    @staticmethod
    def music_for(script: Dict, seconds: float, out: Path) -> Optional[str]:
        if not config.MUSIC_ENABLED:
            return None
        tracks = sorted(Path(REPO / config.MUSIC_DIR).glob("*.mp3"))
        if tracks:
            pick = tracks[zlib.crc32(script.get("title", "").encode()) % len(tracks)]
            shutil.copy(pick, out / "music.mp3")
            return str(out / "music.mp3")
        return make_bed(str(out / "music.wav"), seconds, seed=script.get("title", ""))

    # ── public ───────────────────────────────────────────────────────────────
    def render(self, script: Dict, out_dir: str, enforce_length: bool = True) -> Dict:
        from scripts.qa_video import run_qa

        t0 = time.time()
        out = Path(out_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        safe, repairs = validate_and_repair(script)
        if repairs:
            logger.info(f"[kids] {len(repairs)} scene repairs (see report)")

        voiced, audio, sr = self.voice_lines(safe, out / "lines")
        TL = TLB.build(safe, voiced)
        total = TL["duration"]
        logger.info(f"[kids] narration {total:.1f}s, {len(TL['scenes'])} scenes, {word_count(safe)} words")
        if enforce_length and total > config.KIDS_MAX_SECONDS:
            raise RuntimeError(f"too long: {total:.0f}s > KIDS_MAX_SECONDS={config.KIDS_MAX_SECONDS}")
        (out / "timeline.json").write_text(json.dumps(TL, ensure_ascii=False))

        voice_wav = out / "voice.wav"
        self.assemble_voice(audio, TL["gaps"], sr, voice_wav)
        music = self.music_for(safe, total, out)

        video = out / "video.mp4"
        logger.info("[kids] rendering frames…")
        R.video(TL, str(voice_wav), str(video), music, channel=config.CHANNEL_NAME)

        qa = run_qa(str(video), expected=total, min_duration=config.KIDS_MIN_SECONDS if enforce_length else None)
        qa["checks"].append({"name": "max_duration", "ok": (not enforce_length) or total <= config.KIDS_MAX_SECONDS + 1,
                             "detail": f"{total:.1f}s (max {config.KIDS_MAX_SECONDS}s)"})
        qa["passed"] = all(c["ok"] for c in qa["checks"])
        (out / "qa.json").write_text(json.dumps(qa, indent=2))
        for c in qa["checks"]:
            logger.info(f"[qa] {'✓' if c['ok'] else '✗'} {c['name']}: {c['detail']}")
        if not qa["passed"]:
            raise RuntimeError("video failed QA: " + ", ".join(c["name"] for c in qa["checks"] if not c["ok"]))

        thumb_png, thumb = out / "thumbnail.png", out / "thumbnail.jpg"
        R.thumbnail(safe, str(thumb_png), channel=config.CHANNEL_NAME)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(thumb_png), "-vf", "scale=1280:720",
                        "-q:v", "3", str(thumb)], check=True)
        thumb_png.unlink(missing_ok=True)

        pages = caption_pages([{"start": 0.0, "duration": 0.0, "emphasis": [],
                                "words": [(w, a, b) for w, a, b in ln["words"]]}
                               for sc in TL["scenes"] for ln in sc["lines"]])
        (out / "captions.srt").write_text(srt(pages), encoding="utf-8")
        contact = self.contact_sheet(TL, out)
        short = self.make_short(safe, out) if config.KIDS_SHORTS else None
        report = {"duration_s": round(total, 2), "scenes": len(TL["scenes"]), "words": word_count(safe),
                  "render_seconds": round(time.time() - t0, 1), "repairs": repairs, "voice": self.voice().name,
                  "scene_counts": _counts(s["type"] for s in TL["scenes"]), "qa": qa, "short": bool(short)}
        (out / "render_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        shutil.rmtree(out / "lines", ignore_errors=True)
        logger.info(f"[kids] ✓ {video} ({total:.0f}s) in {report['render_seconds']}s")
        return {"video_path": str(video), "thumbnail_path": str(thumb), "captions_path": str(out / "captions.srt"),
                "contact_sheet": contact, "short_path": short, "duration": total, "report": report, "script": safe}

    def make_short(self, script: Dict, out: Path) -> Optional[str]:
        """Vertical 9:16 Short: its own 30-40 s script (script["short"], hook line first) or, without
        one, a cut of the story's start. Returns its path, or None if it can't be made — a failed
        Short must never block the main video."""
        from agents.kids import short as S
        from agents.kids_script_agent import finish_short, short_cut
        from scripts.qa_video import run_qa

        path, work = out / "short.mp4", out / "short_work"
        try:
            hook = S.card_title(script.get("title", ""))
            hook = hook if hook.endswith("?") else ""
            scenes = (script.get("short") or {}).get("scenes")
            scenes = finish_short(scenes, hook) if scenes else short_cut(script, hook)
            mini, _ = validate_and_repair({"title": script.get("title", ""), "backdrop": script.get("backdrop", "meadow"),
                                           "scenes": scenes})
            work.mkdir(parents=True, exist_ok=True)
            voiced, audio, sr = self.voice_lines(mini, work / "lines")
            TL = TLB.build(mini, voiced)
            total = TL["duration"]
            if total > S.MAX_SECONDS:
                raise RuntimeError(f"{total:.0f}s is over the {S.MAX_SECONDS}s Shorts limit")
            self.assemble_voice(audio, TL["gaps"], sr, work / "voice.wav")
            music = self.music_for(mini, total, work)
            logger.info(f"[kids-short] {total:.0f}s, {len(TL['scenes'])} scenes, {word_count(mini)} words — rendering…")
            R.video(TL, str(work / "voice.wav"), str(work / "wide.mp4"), music, channel="")
            title = S.card_title(script.get("title", ""))
            S.video(TL, str(work / "wide.mp4"), str(path), title, channel=config.CHANNEL_NAME)
            qa = run_qa(str(path), expected=total, resolution=(S.SW, S.SH))
            (out / "short_qa.json").write_text(json.dumps(qa, indent=2))
            if not qa["passed"]:
                raise RuntimeError("failed QA: " + ", ".join(c["name"] for c in qa["checks"] if not c["ok"]))
            S.still(TL, TL["scenes"][min(1, len(TL["scenes"]) - 1)]["end"] - 0.5, str(out / "short_still.png"),
                    title, config.CHANNEL_NAME)
            logger.info(f"[kids-short] ✓ {path} ({total:.0f}s)")
            return str(path)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[kids-short] not made: {e}")
            path.unlink(missing_ok=True)
            return None
        finally:
            shutil.rmtree(work, ignore_errors=True)

    @staticmethod
    def contact_sheet(TL: Dict, out: Path) -> str:
        """One still per scene (late in the scene) in a grid — quick visual review in CI artifacts."""
        from PIL import Image

        tiles = []
        for i, sc in enumerate(TL["scenes"]):
            t = sc["start"] + (sc["end"] - sc["start"]) * 0.8
            p = out / f"_still_{i:02d}.png"
            R.still(TL, t, str(p), config.CHANNEL_NAME)
            tiles.append(p)
        cols = 4
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 480, rows * 270), "white")
        for i, p in enumerate(tiles):
            sheet.paste(Image.open(p).resize((480, 270)), ((i % cols) * 480, (i // cols) * 270))
            p.unlink(missing_ok=True)
        path = out / "contact_sheet.jpg"
        sheet.save(path, quality=85)
        return str(path)


def _counts(items) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def short_meta(full: Dict, full_url: str) -> Dict:
    """Title, description and tags for the Short of a full kids video."""
    base = full["title"].split(" (")[0].strip()
    return {"title": f"{base[:70]} | Explained Like You're 5 #Shorts",
            "description": f"Watch the full video: {full_url}\n\n{full.get('description', '')}\n\n#Shorts"[:4900],
            "tags": full.get("tags", [])}


def earlier_videos(limit: int = 3, skip_url: str = "") -> list:
    """Newest full kids videos already uploaded (from the posted log), for description links."""
    try:
        log = json.loads(Path(config.POSTED_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return []
    kids = [v for v in log if "(Explained Like You're 5)" in v.get("title", "") and v.get("url") and v["url"] != skip_url]
    return [{"title": v["title"].split(" (")[0], "url": v["url"]} for v in kids[-limit:][::-1]]


def description_for(script: Dict, skip_url: str = "") -> str:
    parts = [script.get("description", "").strip()]
    amap = (script.get("analogy") or {}).get("map") or []
    if amap:
        parts.append("Grown-up words in this video:\n" + "\n".join(
            f"- {m.get('real', '')} = {m.get('kid', '')}" for m in amap if isinstance(m, dict)))
    parts.append("Explained Like You're 5 — big ideas, told simply, for curious people of all ages.")
    more = earlier_videos(skip_url=skip_url)
    if more:
        parts.append("More Explained Like You're 5:\n" + "\n".join(f"- {v['title']}: {v['url']}" for v in more))
    if config.CHANNEL_URL:
        parts.append(f"A new one every day. Subscribe: {config.CHANNEL_URL}?sub_confirmation=1")
    parts.append("Narration voice is AI-generated. Animation is made with code. This is not financial advice.")
    return "\n\n".join(p for p in parts if p)[:4900].replace("<", "").replace(">", "")


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="outputs/kids_test")
    ap.add_argument("--no-length-check", action="store_true")
    a = ap.parse_args()
    res = KidsAgent().render(json.loads(Path(a.script).read_text()), a.out, enforce_length=not a.no_length_check)
    print(json.dumps({k: v for k, v in res.items() if k not in ("script", "report")}, indent=2))


if __name__ == "__main__":
    main()
