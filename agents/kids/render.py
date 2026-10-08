"""Timeline → frames (pycairo) → ffmpeg. Also stills and the thumbnail."""

import logging
import math
import subprocess
from pathlib import Path
from typing import Dict, Optional

import cairo

from agents.kids import draw as D
from agents.kids.cast import kid
from agents.kids.draw import INK, PINK, H, W, T, card, col, pop, text
from agents.kids.props import prop
from agents.kids.scenes import SCENES

logger = logging.getLogger(__name__)
FPS = 30


def scene_at(TL: Dict, t: float) -> Dict:
    cur = TL["scenes"][0]
    for sc in TL["scenes"]:
        if t >= sc["start"] - (0.5 if sc is TL["scenes"][0] else 0.0):
            cur = sc
    return cur


def caption(c, TL: Dict, t: float) -> None:
    for sc in TL["scenes"]:
        for ln in sc["lines"]:
            if not (ln["start"] - 0.1 <= t <= ln["start"] + ln["dur"] + 0.3):
                continue
            words = ln["words"] or [(w, ln["start"], ln["start"]) for w in ln["text"].split()]
            size = 46
            c.select_font_face(D.FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            c.set_font_size(size)
            rows, cur = [], []
            for w in words:
                test = " ".join(x[0] for x in cur + [w])
                if cur and c.text_extents(test).x_advance > 1500:
                    rows.append(cur)
                    cur = [w]
                else:
                    cur.append(w)
            rows.append(cur)
            rows = rows[:3]
            bh = 30 + len(rows) * 62
            D.rr(c, W / 2 - 820, H - 30 - bh, 1640, bh, 34)
            col(c, INK, 0.82)
            c.fill()
            for ri, row in enumerate(rows):
                wid = c.text_extents(" ".join(x[0] for x in row)).x_advance
                x = W / 2 - wid / 2
                y = H - 30 - bh + 15 + 31 + ri * 62
                for w, ws, _ in row:
                    c.move_to(x, y + size * 0.35)
                    col(c, "#ffd166" if t >= ws else "#ffffff")
                    c.show_text(w)
                    x += c.text_extents(w + " ").x_advance
            return


def frame(c, TL: Dict, t: float, channel: str = "", captions: bool = True) -> None:
    sc = scene_at(TL, t)
    lt = t - sc["start"]
    S = {"props": sc["props"], "beats": sc["beats"], "dur": sc["end"] - sc["start"], "weather": sc["weather"]}
    D.background(c, t, sc["weather"], TL.get("backdrop", "meadow"))
    try:
        SCENES[sc["type"]](c, lt, S)
    except Exception as e:  # noqa: BLE001 — a broken scene must not kill a 2-minute render
        logger.debug(f"scene {sc['type']} failed at {lt:.2f}s: {e}")
    if captions:
        caption(c, TL, t)
    for nxt in TL["scenes"][1:]:
        d = t - nxt["start"]
        if -0.25 < d < 0.3:
            c.rectangle(0, 0, W, H)
            col(c, "#ffffff", max(0.0, 1 - abs(d) / 0.3) * 0.85)
            c.fill()
    if t < 0.4:
        c.rectangle(0, 0, W, H)
        col(c, "#ffffff", 1 - t / 0.4)
        c.fill()
    if channel:
        text(c, channel, W - 40, 44, 30, "#ffffff", align="r", outline=INK, olw=6)


def _surface():
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    c = cairo.Context(s)
    c.set_antialias(cairo.ANTIALIAS_GOOD)
    return s, c


def still(TL: Dict, t: float, path: str, channel: str = "") -> None:
    D.ensure_fonts()
    s, c = _surface()
    frame(c, TL, t, channel)
    s.write_to_png(path)


def video(TL: Dict, voice_wav: str, out_mp4: str, music_wav: Optional[str] = None, channel: str = "",
          music_volume: float = 0.08, fps: int = FPS) -> None:
    D.ensure_fonts()
    dur = TL["duration"]
    n = int(math.ceil(dur * fps))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-i", voice_wav]
    if music_wav:
        cmd += ["-stream_loop", "-1", "-i", music_wav, "-filter_complex",
                f"[2:a]volume={music_volume},afade=t=in:d=1.5,afade=t=out:st={max(0, dur - 2.5):.2f}:d=2.5[m];"
                f"[1:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.84:level=false[a]", "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-b:a", "160k", "-t", f"{dur:.3f}", "-movflags", "+faststart", out_mp4]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    s, c = _surface()
    try:
        for i in range(n):
            c.save()
            frame(c, TL, i / fps, channel)
            c.restore()
            s.flush()
            ff.stdin.write(bytes(s.get_data()))
            if i % (fps * 20) == 0:
                logger.info(f"[kids] frame {i}/{n}")
    finally:
        ff.stdin.close()
        rc = ff.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed with code {rc}")


def thumbnail(script: Dict, path: str, channel: str = "") -> None:
    """1280x720 JPEG-ready PNG: the question, the cast and the analogy's main prop."""
    D.ensure_fonts()
    s, c = _surface()
    D.background(c, 0.8, "sunny", script.get("backdrop", "meadow"))
    main_prop = "star"
    for sc in script.get("scenes", []):
        p = sc.get("props", {})
        for k in ("place", "whole", "thing", "item", "dream"):
            if p.get(k):
                main_prop = p[k]
                break
        if main_prop != "star":
            break
    q = (script.get("thumbnail_text") or script.get("title", "")).upper()
    with T(c, 700, 330):
        card(c, 0, 0, 1260, 470, "#ffffff", INK, 12, 70)
        D.text_block(c, q, 0, -20, 120, INK, max_w=1160, max_rows=3)
    with T(c, 700, 610):
        card(c, 0, 0, 760, 100, PINK, INK, 8, 50)
        text(c, "EXPLAINED LIKE YOU'RE 5", 0, 0, 52, "#ffffff", max_w=700)
    prop(c, main_prop, 1560, 380, 380, 0.5)
    kid(c, "mia", 1480, 1030, 1.2, 1.0, wave=0.0, bounce=False, mood="wow")
    kid(c, "leo", 1760, 1030, 1.1, 1.0, bounce=False)
    if channel:
        text(c, channel, 60, 1010, 44, "#ffffff", align="l", outline=INK, olw=8)
    s.write_to_png(path)
