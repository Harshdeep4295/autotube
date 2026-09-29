"""
POC — shot-based faceless video renderer (free stack).

Replaces "one still image per section" with a new visual every sentence (~4–7s):
  • broll shots  → Pexels video → Pixabay video → Pollinations image → kinetic text card
  • image shots  → Pollinations image (slow, smooth push-in) → kinetic text card
  • text shots   → kinetic text card (animated gradient + headline), always local

Voice is Kokoro-82M (Apache-2.0, runs offline on CPU). Each shot's line is
synthesized separately, so every shot's length is the exact length of its own
narration — picture and voice cannot drift apart.

Robustness rules (the bugs that broke the old renderer):
  • A shot is never dropped: every provider failure falls through to a local card,
    and if even that fails, to a solid-colour segment.
  • Segments are written to a temp file and renamed only after ffprobe validates them.
  • FFmpeg timeouts scale with shot length.
  • The final video must match the narration length or the run fails loudly.

Usage:
    .venv/bin/python poc/shot_video.py poc/sample_script.json
    PEXELS_API_KEY=... PIXABAY_API_KEY=... .venv/bin/python poc/shot_video.py script.json --out outputs/poc
"""

import argparse
import hashlib
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import requests
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger("poc")

W, H, FPS = 1920, 1080, 30
XF_FRAMES = 12                 # 0.4s crossfade between shots
PAUSE_S = 0.28                 # breath after each line
ACCENT = (255, 210, 63)        # yellow
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
PALETTES = [
    ("0x0b1026", "0x1d2b6b", "0x3a1c71"),
    ("0x08141f", "0x0f3d4c", "0x1b6b73"),
    ("0x160a24", "0x3b1450", "0x6b1b5a"),
    ("0x0d0d0d", "0x1f2a44", "0x283e51"),
]
TRANSITIONS = ["fade", "smoothleft", "fade", "slideup", "fade", "smoothright", "dissolve"]


# ── small helpers ──────────────────────────────────────────────────────────────

def run_ffmpeg(args: List[str], timeout: float, cwd: Optional[Path] = None) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    res = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=cwd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.decode(errors="replace")[-600:])


def probe_duration(path: Path, stream: str = "v") -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", f"{stream}:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, timeout=30,
    )
    out = res.stdout.decode().strip()
    return float(out) if out and out != "N/A" else 0.0


def font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, start: int, min_size: int = 60):
    size = start
    while size > min_size:
        f = font(size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 6
    return font(min_size)


# ── voice (Kokoro, offline) ────────────────────────────────────────────────────

def ensure_kokoro() -> Path:
    model_dir = Path(os.getenv("KOKORO_DIR", Path.home() / ".cache" / "autotube" / "kokoro"))
    model_dir.mkdir(parents=True, exist_ok=True)
    for name in KOKORO_FILES:
        dest = model_dir / name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            continue
        logger.info(f"Downloading Kokoro model file {name} …")
        tmp = dest.with_suffix(".part")
        with requests.get(KOKORO_URL + name, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        tmp.rename(dest)
    return model_dir


def synth_voice(shots: List[Dict], out_dir: Path, voice: str, speed: float):
    """Synthesize each shot's line; return (wav_path, shot_durations, speech_durations)."""
    from kokoro_onnx import Kokoro

    model_dir = ensure_kokoro()
    tts = Kokoro(str(model_dir / KOKORO_FILES[0]), str(model_dir / KOKORO_FILES[1]))
    pieces, durs, speech = [], [], []
    sr = 24000
    for i, shot in enumerate(shots):
        samples, sr = tts.create(shot["text"], voice=voice, speed=speed, lang="en-us")
        pad = np.zeros(int(sr * PAUSE_S), dtype=samples.dtype)
        pieces += [samples, pad]
        speech.append(len(samples) / sr)
        durs.append((len(samples) + len(pad)) / sr)
        logger.info(f"  voice {i+1:02d}/{len(shots)}  {speech[-1]:5.2f}s  {shot['text'][:60]}")
    raw = out_dir / "voice_raw.wav"
    sf.write(raw, np.concatenate(pieces), sr)
    # Loudness-normalize in its own pass: inside a split/mix graph loudnorm drops its
    # last ~3s (lookahead buffer never flushed), which cut the end of the narration.
    wav = out_dir / "voice.wav"
    run_ffmpeg(["-i", str(raw), "-af", "aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", str(wav)], 300)
    return wav, durs, speech


# ── media providers (all free) ─────────────────────────────────────────────────

class MediaFetcher:
    def __init__(self, cache_dir: Path):
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)
        self.pexels_key = os.getenv("PEXELS_API_KEY", "")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY", "")
        self.used_ids: set = set()
        self.dead: set = set()   # providers that failed at network level — stop retrying them

    def _download(self, url: str, dest: Path, headers: Optional[Dict] = None) -> Optional[Path]:
        tmp = dest.with_suffix(dest.suffix + ".part")
        with requests.get(url, headers=headers or {}, stream=True, timeout=(10, 60)) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        tmp.rename(dest)
        return dest

    def _guard(self, provider: str, fn, *args) -> Optional[Path]:
        if provider in self.dead:
            return None
        try:
            return fn(*args)
        except requests.exceptions.ConnectionError as e:
            self.dead.add(provider)
            logger.warning(f"    {provider}: unreachable ({str(e)[:80]}) — disabled for this run")
        except Exception as e:
            logger.warning(f"    {provider}: {type(e).__name__}: {str(e)[:120]}")
        return None

    def pexels_video(self, query: str, min_dur: float) -> Optional[Path]:
        if not self.pexels_key:
            return None
        def go():
            r = requests.get(
                "https://api.pexels.com/videos/search",
                params={"query": query, "orientation": "landscape", "per_page": 15},
                headers={"Authorization": self.pexels_key}, timeout=15,
            )
            r.raise_for_status()
            for v in r.json().get("videos", []):
                if v["id"] in self.used_ids or v.get("duration", 0) < min(min_dur, 5):
                    continue
                files = [f for f in v["video_files"] if f.get("width") and f["width"] >= 1280
                         and f.get("file_type") == "video/mp4"]
                if not files:
                    continue
                best = min(files, key=lambda f: abs(f["width"] - 1920))
                dest = self.cache / f"pexels_{v['id']}_{best['width']}.mp4"
                if not dest.exists():
                    self._download(best["link"], dest)
                if probe_duration(dest) > 1:
                    self.used_ids.add(v["id"])
                    return dest
            return None
        return self._guard("pexels", go)

    def pixabay_video(self, query: str, min_dur: float) -> Optional[Path]:
        if not self.pixabay_key:
            return None
        def go():
            r = requests.get(
                "https://pixabay.com/api/videos/",
                params={"key": self.pixabay_key, "q": query, "per_page": 15, "safesearch": "true"},
                timeout=15,
            )
            r.raise_for_status()
            for hit in r.json().get("hits", []):
                if hit["id"] in self.used_ids or hit.get("duration", 0) < min(min_dur, 5):
                    continue
                vid = hit["videos"].get("large") or hit["videos"].get("medium")
                if not vid or not vid.get("url"):
                    continue
                dest = self.cache / f"pixabay_{hit['id']}.mp4"
                if not dest.exists():
                    self._download(vid["url"], dest)
                if probe_duration(dest) > 1:
                    self.used_ids.add(hit["id"])
                    return dest
            return None
        return self._guard("pixabay", go)

    def pollinations_image(self, prompt: str) -> Optional[Path]:
        def go():
            key = hashlib.md5(prompt.encode()).hexdigest()[:12]
            dest = self.cache / f"img_{key}.jpg"
            if not dest.exists():
                url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
                       + f"?width={W}&height={H}&nologo=true&model=flux&seed={int(key[:6], 16)}")
                self._download(url, dest)
            with Image.open(dest) as im:   # rejects HTML error pages saved as .jpg
                im.verify()
            return dest
        path = self._guard("pollinations", go)
        if path is None:
            for p in self.cache.glob("img_*.jpg*"):
                if p.stat().st_size < 5000:
                    p.unlink(missing_ok=True)
        return path

    def resolve(self, visual: Dict, dur: float) -> Dict:
        kind = visual.get("type", "text")
        if kind == "broll":
            q = visual["query"]
            for provider, fn in (("pexels", lambda: self.pexels_video(q, dur)),
                                 ("pixabay", lambda: self.pixabay_video(q, dur))):
                p = fn()
                if p:
                    return {"kind": "video", "path": p, "provider": provider}
            p = self.pollinations_image(q + ", cinematic photo, natural light")
            if p:
                return {"kind": "image", "path": p, "provider": "pollinations"}
        elif kind == "image":
            p = self.pollinations_image(visual["prompt"])
            if p:
                return {"kind": "image", "path": p, "provider": "pollinations"}
        return {"kind": "card", "path": None, "provider": "local" if kind == "text" else "fallback"}


# ── graphics (Pillow) ──────────────────────────────────────────────────────────

def render_card_png(headline: str, sub: str, out: Path, label: str = "") -> None:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hf = fit_font(d, headline, W - 360, 150)
    hw = d.textlength(headline, font=hf)
    hb = d.textbbox((0, 0), headline, font=hf)
    h_h = hb[3] - hb[1]
    y = H // 2 - h_h - 10 - hb[1]

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text(((W - hw) / 2 + 6, y + 8), headline, font=hf, fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    d.text(((W - hw) / 2, y), headline, font=hf, fill=(255, 255, 255, 255))

    bar_w = min(int(hw * 0.35), 420)
    bar_y = y + hb[3] + 34
    d.rounded_rectangle([(W - bar_w) / 2, bar_y, (W + bar_w) / 2, bar_y + 10], radius=5, fill=(*ACCENT, 255))
    if sub:
        sf_ = fit_font(d, sub, W - 420, 58, 36)
        sw = d.textlength(sub, font=sf_)
        d.text(((W - sw) / 2, bar_y + 40), sub, font=sf_, fill=(225, 230, 240, 235))
    if label:
        lf = font(28)
        lw = d.textlength(label, font=lf)
        d.rounded_rectangle([40, H - 96, 40 + lw + 40, H - 44], radius=12, fill=(0, 0, 0, 150))
        d.text((60, H - 88), label, font=lf, fill=(255, 255, 255, 200))
    img.save(out)


def render_dots_png(out: Path) -> None:
    if out.exists():
        return
    img = Image.new("RGBA", (W + 120, H + 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in range(0, W + 120, 60):
        for y in range(0, H + 120, 60):
            d.ellipse([x, y, x + 3, y + 3], fill=(255, 255, 255, 38))
    img.save(out)


# ── segment rendering ─────────────────────────────────────────────────────────

ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]


def seg_card(out: Path, n_frames: int, card_png: Path, dots_png: Path, palette, timeout: float) -> None:
    L = n_frames / FPS
    c0, c1, c2 = palette
    grad = f"gradients=s={W}x{H}:r={FPS}:d={L:.3f}:n=3:c0={c0}:c1={c1}:c2={c2}:speed=0.012:type=linear"
    fc = (
        "[1:v]format=rgba[dots];"
        "[0:v][dots]overlay=x='-mod(t*18,60)':y='-mod(t*10,60)'[bg];"
        "[2:v]format=rgba,fade=t=in:st=0.1:d=0.45:alpha=1[card];"
        "[bg][card]overlay=x=0:y='46*max(0,1-(t-0.1)/0.5)',"
        "vignette=PI/5,format=yuv420p[v]"
    )
    run_ffmpeg(["-f", "lavfi", "-i", grad,
                "-loop", "1", "-framerate", str(FPS), "-i", str(dots_png),
                "-loop", "1", "-framerate", str(FPS), "-i", str(card_png),
                "-filter_complex", fc, "-map", "[v]", "-frames:v", str(n_frames), *ENC, str(out)], timeout)


def seg_video(out: Path, n_frames: int, clip: Path, timeout: float) -> None:
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,"
          "eq=contrast=1.04:saturation=1.08:brightness=-0.03,format=yuv420p")
    run_ffmpeg(["-stream_loop", "-1", "-i", str(clip), "-vf", vf, "-frames:v", str(n_frames), *ENC, str(out)], timeout)


def seg_image(out: Path, n_frames: int, img: Path, rng: random.Random, timeout: float) -> None:
    # Upscale 2x before zoompan so the motion is sub-pixel smooth (no shimmer/jitter).
    N = n_frames
    moves = [
        ("1.0+0.10*on/{N}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),           # push in
        ("1.10-0.10*on/{N}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),          # pull out
        ("1.10", "(iw-iw/zoom)*on/{N}", "ih/2-(ih/zoom/2)"),                     # pan right
        ("1.10", "(iw-iw/zoom)*(1-on/{N})", "ih/2-(ih/zoom/2)"),                 # pan left
    ]
    z, x, y = (e.replace("{N}", str(N)) for e in rng.choice(moves))
    vf = (f"scale={2*W}:{2*H}:force_original_aspect_ratio=increase,crop={2*W}:{2*H},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={N}:s={W}x{H}:fps={FPS},"
          "eq=contrast=1.04:saturation=1.08:brightness=-0.03,format=yuv420p")
    run_ffmpeg(["-loop", "1", "-framerate", str(FPS), "-i", str(img), "-vf", vf,
                "-frames:v", str(n_frames), *ENC, str(out)], timeout)


def seg_solid(out: Path, n_frames: int) -> None:
    run_ffmpeg(["-f", "lavfi", "-i", f"color=c=0x101828:s={W}x{H}:r={FPS}",
                "-frames:v", str(n_frames), *ENC, str(out)], 120)


def valid_segment(path: Path, n_frames: int) -> bool:
    return path.exists() and abs(probe_duration(path) - n_frames / FPS) < 0.1


def build_segment(i: int, shot: Dict, media: Dict, n_frames: int, work: Path, dots: Path,
                  label_placeholders: bool) -> Dict:
    out = work / f"seg_{i:03d}.mp4"
    tmp = work / f"seg_{i:03d}.tmp.mp4"
    rng = random.Random(i)
    timeout = 90 + 3.0 * n_frames / FPS
    visual = shot.get("visual", {})
    attempts = []
    if media["kind"] == "video":
        attempts.append(("video", lambda: seg_video(tmp, n_frames, media["path"], timeout)))
    if media["kind"] == "image":
        attempts.append(("image", lambda: seg_image(tmp, n_frames, media["path"], rng, timeout)))

    # Card is both the designed look for text shots and the fallback for everything else.
    if visual.get("type") == "text":
        headline, sub = visual.get("headline", ""), visual.get("sub", "")
    else:
        headline = (shot.get("emphasis") or [""])[0].upper()
        sub = ""
    label = ""
    if label_placeholders and visual.get("type") in ("broll", "image") and media["kind"] == "card":
        label = ("PLACEHOLDER · stock clip: " + visual.get("query", "")) if visual["type"] == "broll" \
            else ("PLACEHOLDER · AI image: " + visual.get("prompt", "")[:60])
    card_png = work / f"card_{i:03d}.png"
    render_card_png(headline, sub, card_png, label)
    attempts.append(("card", lambda: seg_card(tmp, n_frames, card_png, dots, PALETTES[i % len(PALETTES)], timeout)))
    attempts.append(("solid", lambda: seg_solid(tmp, n_frames)))

    for name, fn in attempts:
        try:
            tmp.unlink(missing_ok=True)
            fn()
            if valid_segment(tmp, n_frames):
                tmp.rename(out)
                return {"index": i, "path": out, "rendered_as": name}
            logger.warning(f"  seg {i}: {name} produced wrong length — trying next")
        except Exception as e:
            logger.warning(f"  seg {i}: {name} failed: {str(e)[:160]}")
    raise RuntimeError(f"segment {i}: every render attempt failed")


# ── captions (ASS, burned in) ─────────────────────────────────────────────────

def ass_time(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def write_captions(shots: List[Dict], starts: List[float], speech: List[float], path: Path) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Liberation Sans,68,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,5,2,2,120,120,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    yellow = "{\\c&H3FD2FF&}"   # ASS colours are BGR
    white = "{\\c&HFFFFFF&}"
    for shot, start, sp in zip(shots, starts, speech):
        words = shot["text"].split()
        chunks, cur = [], []
        for w in words:
            cur.append(w)
            if len(cur) >= 4 or re.search(r"[.,?!;:]$", w):
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        total_chars = sum(len(" ".join(c)) for c in chunks) or 1
        emph = [e.lower() for e in shot.get("emphasis", [])]
        t = start + 0.05
        for c in chunks:
            dur = sp * len(" ".join(c)) / total_chars
            text = " ".join(c)
            for e in emph:
                idx = text.lower().find(e.split()[0])
                if idx >= 0:
                    end = idx + len(text[idx:].split()[0]) if len(e.split()) == 1 else len(text)
                    text = text[:idx] + yellow + text[idx:end] + white + text[end:]
                    break
            pop = "{\\fad(60,0)\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)}"
            lines.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + dur)},Cap,,0,0,0,,{pop}{text}")
            t += dur
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


# ── main pipeline ─────────────────────────────────────────────────────────────

def render(script_path: Path, out_root: Path, voice: str, speed: float, music: Optional[Path],
           label_placeholders: bool) -> Path:
    t0 = time.time()
    script = json.loads(script_path.read_text())
    shots = script["shots"]
    run_dir = out_root / time.strftime("%Y%m%d_%H%M%S")
    work = run_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    logger.info(f"[1/5] Voice — {len(shots)} lines with Kokoro ({voice})")
    wav, durs, speech = synth_voice(shots, work, voice, speed)

    # Frame-exact shot boundaries so the cut points never drift from the narration.
    bounds = [0]
    acc = 0.0
    for d in durs:
        acc += d
        bounds.append(round(acc * FPS))
    frames = [bounds[i + 1] - bounds[i] for i in range(len(shots))]
    starts = [b / FPS for b in bounds[:-1]]
    total = bounds[-1] / FPS
    logger.info(f"      narration {total:.1f}s, avg shot {total/len(shots):.1f}s")

    logger.info("[2/5] Media — resolving a visual for every shot")
    fetcher = MediaFetcher(Path(os.getenv("POC_MEDIA_CACHE", out_root / "media_cache")))
    media = []
    for i, shot in enumerate(shots):
        m = fetcher.resolve(shot.get("visual", {}), durs[i])
        media.append(m)
        logger.info(f"  shot {i+1:02d}: {shot.get('visual', {}).get('type', 'text'):5s} → {m['provider']}")

    logger.info("[3/5] Segments — rendering shots")
    dots = work / "dots.png"
    render_dots_png(dots)
    workers = max(1, (os.cpu_count() or 2) // 2)
    jobs = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, shot in enumerate(shots):
            # every shot but the last carries extra frames that the crossfade overlaps
            n = frames[i] + (XF_FRAMES if i < len(shots) - 1 else 0)
            jobs.append(ex.submit(build_segment, i, shot, media[i], n, work, dots, label_placeholders))
        segs = sorted((j.result() for j in jobs), key=lambda s: s["index"])

    logger.info("[4/5] Captions")
    write_captions(shots, starts, speech, work / "captions.ass")

    logger.info("[5/5] Final composite — crossfades + captions + voice + ducked music")
    out = run_dir / "video.mp4"
    args: List[str] = []
    for s in segs:
        args += ["-i", s["path"].name]
    args += ["-i", wav.name]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music.resolve())]
    n = len(segs)
    fc = [f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p[s{i}]" for i in range(n)]
    prev = "s0"
    rng = random.Random(7)
    for i in range(1, n):
        tr = rng.choice(TRANSITIONS)
        fc.append(f"[{prev}][s{i}]xfade=transition={tr}:duration={XF_FRAMES/FPS:.3f}:offset={starts[i]:.4f}[x{i}]")
        prev = f"x{i}"
    fc.append(f"[{prev}]ass=captions.ass[vout]")
    fc.append(f"[{n}:a]aresample=48000,apad=whole_dur={total:.3f},asplit=2[voice][key]")
    if music:
        fc.append(f"[{n+1}:a]aresample=48000,volume=0.22,atrim=0:{total:.3f}[mus]")
        fc.append("[mus][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=450[duck]")
        fc.append(f"[voice][duck]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={total-1.5:.3f}:d=1.5[aout]")
    else:
        fc.append("[key]anullsink;[voice]anull[aout]")
    run_ffmpeg([*args, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart",
                str(out.resolve())], timeout=600 + 4 * total, cwd=work)

    vdur, adur = probe_duration(out, "v"), probe_duration(out, "a")
    if abs(vdur - total) > 0.15 or abs(adur - total) > 0.15:
        raise RuntimeError(f"length check failed: video {vdur:.2f}s, audio {adur:.2f}s, narration {total:.2f}s")

    report = {
        "title": script.get("title"), "duration_s": round(total, 2), "shots": len(shots),
        "render_seconds": round(time.time() - t0, 1),
        "per_shot": [{"i": i + 1, "type": s.get("visual", {}).get("type"), "provider": media[i]["provider"],
                      "rendered_as": segs[i]["rendered_as"], "seconds": round(frames[i] / FPS, 2)}
                     for i, s in enumerate(shots)],
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    logger.info(f"✓ {out}  ({total:.1f}s, {len(shots)} shots, rendered in {report['render_seconds']}s)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path)
    ap.add_argument("--out", type=Path, default=Path("outputs/poc"))
    ap.add_argument("--voice", default="am_michael", help="Kokoro voice, e.g. am_michael, af_heart, bm_george")
    ap.add_argument("--speed", type=float, default=1.05)
    ap.add_argument("--music", type=Path, default=Path("data/music/ambient_01.mp3"))
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--label-placeholders", action="store_true",
                    help="Tag shots that fell back to a card with the stock clip/image they were meant to show")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    music = None if a.no_music or not a.music.exists() else a.music
    render(a.script, a.out, a.voice, a.speed, music, a.label_placeholders)


if __name__ == "__main__":
    main()
