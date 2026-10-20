"""
Vertical 9:16 Short cut from a rendered explainer, made with one FFmpeg pass (no second render).

Shorts bring most of the channel's views, while the long explainers are found mainly by search.
The Short is the explainer's opening (its hook, cut at a shot boundary, at most 58 s) laid out for
a phone: channel name and title on top, the animation in a band across the middle, large
captions below it, and "Full video on the channel" at the bottom. The upload's description
links the full video.

    python -m agents.explainer_short outputs/<job>      # writes outputs/<job>/short.mp4
"""

import json
import logging
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SW, SH = 1080, 1920
MAX_SECONDS = 58.0          # Shorts may run up to 3 min, but under a minute is what gets swiped to the end
MIN_SECONDS = 20.0
# The 16:9 frame minus the bottom caption band (theme.ts SAFE: scenes live in x 110-1810, y 90-850).
CROP_X, CROP_Y, CROP_W, CROP_H = 110, 60, 1700, 800
BAND_W = 1040
BAND_H = round(BAND_W * CROP_H / CROP_W / 2) * 2      # 490
BORDER = 6
BAND_X, BAND_Y = (SW - BAND_W) // 2 - BORDER, 640
NAVY, CYAN, YELLOW, WHITE = "070b1a", "4fd1c5", "ffd23f", "f4f6fb"
FONT = "Liberation Sans"


def pick_cut(shots: List[Dict], max_s: float = MAX_SECONDS, min_s: float = MIN_SECONDS) -> Optional[float]:
    """End time of the Short: the end of the first chapter (the hook) if it fits, else the last
    shot that ends by max_s. None if not even min_s fits at a shot boundary."""
    ends = [float(s["start"]) + float(s["duration"]) for s in shots]
    for i, s in enumerate(shots[1:], 1):
        if s.get("chapter"):
            hook_end = ends[i - 1]
            if min_s <= hook_end <= max_s:
                return round(hook_end, 3)
            break
    fits = [e for e in ends if e <= max_s]
    if fits and fits[-1] >= min_s:
        return round(fits[-1], 3)
    return None


def parse_srt(text: str) -> List[Tuple[float, float, str]]:
    def secs(t: str) -> float:
        h, m, rest = t.strip().replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest)

    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.strip().splitlines() if ln.strip()]
        for j, ln in enumerate(lines):
            if "-->" in ln:
                a, b = ln.split("-->")
                body = " ".join(lines[j + 1:]).strip()
                if body:
                    out.append((secs(a), secs(b), body))
                break
    return out


def _ass_time(t: float) -> str:
    cs = max(0, int(round(t * 100)))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _ass_text(t: str) -> str:
    return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _colour(hex6: str) -> str:
    """ASS colours are &HAABBGGRR."""
    r, g, b = hex6[0:2], hex6[2:4], hex6[4:6]
    return f"&H00{b}{g}{r}".upper()


def wrap_title(title: str, width: int = 20, rows: int = 3) -> List[str]:
    lines = textwrap.wrap(title, width=width) or [title]
    if len(lines) > rows:
        lines = lines[:rows]
        lines[-1] = lines[-1].rstrip(" ,.:;-") + "…"
    return lines


def build_ass(title: str, channel: str, captions: List[Tuple[float, float, str]], duration: float) -> str:
    """Every text layer of the Short: channel, title, captions and footer, in one subtitle file."""
    end = _ass_time(duration)
    styles = [
        # Name, size, primary colour, outline colour, back colour, bold, border style, outline, alignment, marginV
        ("Channel", 42, _colour(CYAN), _colour(NAVY), _colour(NAVY), -1, 1, 0, 8, 150),
        ("Title", 82, _colour(YELLOW), _colour(NAVY), _colour(NAVY), -1, 1, 3, 8, 250),
        ("Caption", 66, _colour(WHITE), "&H00000000", "&H00000000", -1, 1, 5, 8, 1230),
        ("Footer", 46, _colour(NAVY), _colour(YELLOW), _colour(YELLOW), -1, 3, 22, 2, 430),   # above the Shorts player overlay
    ]
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {SW}", f"PlayResY: {SH}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    for name, size, prim, outl, back, bold, bstyle, outline, align, mv in styles:
        head.append(f"Style: {name},{FONT},{size},{prim},{prim},{outl},{back},{bold},0,0,0,100,100,0,0,"
                    f"{bstyle},{outline},0,{align},100,100,{mv},1")
    ev = ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    if channel:
        ev.append(f"Dialogue: 0,{_ass_time(0)},{end},Channel,,0,0,0,,{_ass_text(channel.upper())}")
    title_text = r"\N".join(_ass_text(x) for x in wrap_title(title))
    ev.append(f"Dialogue: 0,{_ass_time(0)},{end},Title,,0,0,0,,{title_text}")
    for a, b, body in captions:
        if a >= duration:
            break
        ev.append(f"Dialogue: 0,{_ass_time(a)},{_ass_time(min(b, duration))},Caption,,0,0,0,,{_ass_text(body)}")
    ev.append(f"Dialogue: 0,{_ass_time(0)},{end},Footer,,0,0,0,,Full video on the channel")
    return "\n".join(head + ev) + "\n"


def filter_graph(duration: float, ass_path: str) -> str:
    ass = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fade = max(0.0, duration - 0.4)
    return (
        f"color=c=0x{NAVY}:s={SW}x{SH}:r=30:d={duration:.3f}[bg];"
        f"[0:v]trim=0:{duration:.3f},setpts=PTS-STARTPTS,crop={CROP_W}:{CROP_H}:{CROP_X}:{CROP_Y},"
        f"scale={BAND_W}:{BAND_H},pad={BAND_W + 2 * BORDER}:{BAND_H + 2 * BORDER}:{BORDER}:{BORDER}:color=0x{CYAN}[band];"
        f"[bg][band]overlay={BAND_X}:{BAND_Y}:shortest=1,ass='{ass}',format=yuv420p[v];"
        f"[0:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={fade:.3f}:d=0.4[a]"
    )


def make_short(out_dir: str, title: str, channel: str = "") -> Optional[Dict]:
    """Cut out_dir/video.mp4 into out_dir/short.mp4. Returns {"path", "duration"} or None when the
    opening has no shot boundary between MIN_SECONDS and MAX_SECONDS."""
    out = Path(out_dir)
    props = json.loads((out / "props.json").read_text())
    cut = pick_cut(props["shots"])
    if cut is None:
        logger.info("[short] no shot boundary between %.0f and %.0f s — no Short", MIN_SECONDS, MAX_SECONDS)
        return None
    srt_path = out / "captions.srt"
    captions = parse_srt(srt_path.read_text(encoding="utf-8")) if srt_path.exists() else []
    ass_path = out / "short.ass"
    ass_path.write_text(build_ass(title, channel, captions, cut), encoding="utf-8")
    path = out / "short.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "video.mp4"),
           "-filter_complex", filter_graph(cut, str(ass_path)), "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-r", "30",
           "-c:a", "aac", "-b:a", "192k", "-t", f"{cut:.3f}", "-movflags", "+faststart", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {res.stderr.strip()[-600:]}")
    return {"path": str(path), "duration": cut}


def short_meta(full: Dict, full_url: str) -> Dict:
    """Title, description and tags for the Short of an explainer."""
    title = str(full.get("title", "")).strip()
    first_para = str(full.get("description", "")).strip().split("\n\n")[0]
    desc = f"Watch the full video: {full_url}\n\n{first_para}\n\n#Shorts" if full_url else f"{first_para}\n\n#Shorts"
    return {"title": f"{title[:90]} #Shorts", "description": desc[:4900].replace("<", "").replace(">", ""),
            "tags": full.get("tags", [])}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    job = Path(sys.argv[1])
    script = json.loads((job / "script.json").read_text())
    print(make_short(str(job), script.get("title", ""), "Run It Local"))
