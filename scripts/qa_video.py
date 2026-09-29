"""
Automated video QA — runs after every render; a failed check blocks the upload.

    python scripts/qa_video.py outputs/<job>/video.mp4 --expected 512.3 --min 480

Checks: stream specs, video/audio/narration lengths agree, no black gaps, no frozen
picture, loudness near −16 LUFS with a safe true peak, minimum length.
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Dict, List, Optional

SPEC = {"width": 1920, "height": 1080, "fps": 30.0, "vcodec": "h264", "acodec": "aac"}
LUFS_TARGET, LUFS_TOL, TRUE_PEAK_MAX = -16.0, 2.0, -0.5
BLACK_MAX_S, FREEZE_MAX_S = 0.5, 4.0


def _run(cmd: List[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(path: str) -> Dict:
    r = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path], 60)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {r.stderr[-300:]}")
    return json.loads(r.stdout)


def _fps(rate: str) -> float:
    n, _, d = rate.partition("/")
    return float(n) / float(d or 1) if float(d or 1) else 0.0


def analyze(path: str) -> Dict:
    """One decode pass for black/freeze detection, one for loudness."""
    vf = f"blackdetect=d={BLACK_MAX_S}:pix_th=0.03,freezedetect=n=0.0005:d={FREEZE_MAX_S}"
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf", vf, "-an", "-f", "null", "-"])
    blacks = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]
    freezes = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", r.stderr)]
    open_freeze = len(re.findall(r"freeze_start", r.stderr)) > len(freezes)
    a = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = a.stderr[a.stderr.rfind("Summary:"):] if "Summary:" in a.stderr else ""
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return {
        "blacks": blacks,
        "freezes": freezes,
        "open_freeze": open_freeze,
        "lufs": float(lufs.group(1)) if lufs else None,
        "true_peak": (float(peak.group(1)) if peak and peak.group(1) != "-inf" else None),
    }


def run_qa(path: str, expected: Optional[float] = None, min_duration: Optional[float] = None) -> Dict:
    checks = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    info = probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    check("has_video", v is not None, "video stream present" if v else "no video stream")
    check("has_audio", a is not None, "audio stream present" if a else "no audio stream")
    if not v or not a:
        return {"passed": False, "checks": checks}

    vd, ad = float(v.get("duration", 0)), float(a.get("duration", 0))
    check("resolution", (v["width"], v["height"]) == (SPEC["width"], SPEC["height"]), f"{v['width']}x{v['height']}")
    fps = _fps(v.get("r_frame_rate", "0/1"))
    check("fps", abs(fps - SPEC["fps"]) < 0.01, f"{fps:.2f} fps")
    check("codecs", v["codec_name"] == SPEC["vcodec"] and a["codec_name"] == SPEC["acodec"],
          f"{v['codec_name']} + {a['codec_name']}")
    check("av_length_match", abs(vd - ad) <= 0.15, f"video {vd:.2f}s, audio {ad:.2f}s")
    if expected is not None:
        check("narration_length_match", abs(vd - expected) <= 0.15, f"video {vd:.2f}s vs narration {expected:.2f}s")
    if min_duration:
        check("min_length", vd >= min_duration, f"{vd:.0f}s (min {min_duration:.0f}s)")

    an = analyze(path)
    long_blacks = [b for b in an["blacks"] if b[1] - b[0] > BLACK_MAX_S]
    check("no_black_gaps", not long_blacks, f"black segments: {long_blacks[:3]}" if long_blacks else "none")
    long_freezes = [f for f in an["freezes"] if f > FREEZE_MAX_S] + ([-1.0] if an["open_freeze"] else [])
    check("no_frozen_picture", not long_freezes, f"freezes: {long_freezes[:3]}" if long_freezes else "none")
    lufs, tp = an["lufs"], an["true_peak"]
    check("loudness", lufs is not None and abs(lufs - LUFS_TARGET) <= LUFS_TOL,
          f"{lufs} LUFS (target {LUFS_TARGET}±{LUFS_TOL})")
    check("true_peak", tp is not None and tp <= TRUE_PEAK_MAX, f"{tp} dBFS (max {TRUE_PEAK_MAX})")
    return {"passed": all(c["ok"] for c in checks), "checks": checks, "duration": vd}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--expected", type=float, default=None)
    ap.add_argument("--min", type=float, default=None)
    a = ap.parse_args()
    res = run_qa(a.video, a.expected, a.min)
    for c in res["checks"]:
        print(f"{'✓' if c['ok'] else '✗'} {c['name']:24s} {c['detail']}")
    print("PASSED" if res["passed"] else "FAILED")
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
