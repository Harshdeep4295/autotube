"""Vertical 9:16 cut of a kids video for YouTube Shorts.

Same timeline and audio as the 16:9 video, re-rendered on a 1080x1920 canvas: the question
on top, the animated scene in a band across the middle, and large word-by-word captions
below it (the in-scene captions would be too small on a phone). Content stays inside the
area the Shorts player doesn't cover (title/buttons at the bottom, header at the top).
"""

import logging
import math
import subprocess
from typing import Dict

import cairo

from agents.kids import draw as D
from agents.kids import render as R
from agents.kids.draw import INK, PINK, T, card, col, text

logger = logging.getLogger(__name__)

SW, SH = 1080, 1920
MAX_SECONDS = 180                     # YouTube Shorts limit
BAND_X, BAND_Y, BAND_W = 20, 640, 1040
BAND_H = BAND_W * D.H / D.W           # keeps 16:9 → 585
PAPER = "#fff8e7"
CAPTION_Y, CAPTION_SIZE, CAPTION_LINE_H, CAPTION_MAX_W = 1380, 64, 84, 960


def card_title(title: str) -> str:
    """'What Is a Pension? (Explained Like You're 5)' → 'What Is a Pension?'"""
    return title.split(" (")[0].strip() or title


def _captions(c, TL: Dict, t: float) -> None:
    for sc in TL["scenes"]:
        for ln in sc["lines"]:
            if not (ln["start"] - 0.1 <= t <= ln["start"] + ln["dur"] + 0.3):
                continue
            words = ln["words"] or [(w, ln["start"], ln["start"]) for w in ln["text"].split()]
            c.select_font_face(D.FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            c.set_font_size(CAPTION_SIZE)
            rows, cur = [], []
            for w in words:
                test = " ".join(x[0] for x in cur + [w])
                if cur and c.text_extents(test).x_advance > CAPTION_MAX_W:
                    rows.append(cur)
                    cur = [w]
                else:
                    cur.append(w)
            rows.append(cur)
            rows = rows[:4]
            y0 = CAPTION_Y - (len(rows) - 1) * CAPTION_LINE_H / 2
            for ri, row in enumerate(rows):
                x = SW / 2 - c.text_extents(" ".join(x[0] for x in row)).x_advance / 2
                for w, ws, _ in row:
                    c.move_to(x, y0 + ri * CAPTION_LINE_H + CAPTION_SIZE * 0.35)
                    col(c, PINK if t >= ws else INK)
                    c.show_text(w)
                    x += c.text_extents(w + " ").x_advance
            return


def frame(c, TL: Dict, t: float, title: str, channel: str = "") -> None:
    c.rectangle(0, 0, SW, SH)
    col(c, PAPER)
    c.fill()
    if channel:
        text(c, channel, SW / 2, 150, 34, INK, max_w=900)
    D.text_block(c, title, SW / 2, 345, 88, INK, max_w=960, max_rows=3)
    with T(c, SW / 2, 560):
        card(c, 0, 0, 640, 84, PINK, INK, 6, 42)
        text(c, "EXPLAINED LIKE YOU'RE 5", 0, 0, 42, "#ffffff", max_w=580)

    c.save()
    D.rr(c, BAND_X, BAND_Y, BAND_W, BAND_H, 36)
    c.clip()
    c.translate(BAND_X, BAND_Y)
    c.scale(BAND_W / D.W, BAND_W / D.W)
    R.frame(c, TL, t, "", captions=False)
    c.restore()
    D.rr(c, BAND_X, BAND_Y, BAND_W, BAND_H, 36)
    col(c, INK)
    c.set_line_width(8)
    c.stroke()

    _captions(c, TL, t)


def _surface():
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, SW, SH)
    c = cairo.Context(s)
    c.set_antialias(cairo.ANTIALIAS_GOOD)
    return s, c


def still(TL: Dict, t: float, path: str, title: str, channel: str = "") -> None:
    D.ensure_fonts()
    s, c = _surface()
    frame(c, TL, t, title, channel)
    s.write_to_png(path)


def video(TL: Dict, source_mp4: str, out_mp4: str, title: str, channel: str = "", fps: int = R.FPS) -> None:
    """Render the vertical frames and take the finished audio mix from the 16:9 video."""
    D.ensure_fonts()
    dur = TL["duration"]
    n = int(math.ceil(dur * fps))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{SW}x{SH}",
           "-r", str(fps), "-i", "-", "-i", source_mp4, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy",
           "-t", f"{dur:.3f}", "-movflags", "+faststart", out_mp4]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    s, c = _surface()
    try:
        for i in range(n):
            c.save()
            frame(c, TL, i / fps, title, channel)
            c.restore()
            s.flush()
            ff.stdin.write(bytes(s.get_data()))
            if i % (fps * 20) == 0:
                logger.info(f"[kids-short] frame {i}/{n}")
    finally:
        ff.stdin.close()
        rc = ff.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed with code {rc}")
