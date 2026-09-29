"""QA must catch each defect. Uses tiny synthetic videos (needs ffmpeg)."""
import shutil
import subprocess

import pytest

from scripts.qa_video import run_qa

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def make(path, vf_src, dur=8, audio_dur=None):
    audio_dur = audio_dur or dur
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", vf_src,
                    "-f", "lavfi", "-i", f"sine=frequency=300:duration={audio_dur}",
                    "-t", str(max(dur, audio_dur)), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-shortest" if audio_dur == dur else "-y", str(path)], check=True)
    return str(path)


def by_name(res):
    return {c["name"]: c["ok"] for c in res["checks"]}


def test_moving_picture_passes_structural_checks(tmp_path):
    v = make(tmp_path / "ok.mp4", "testsrc2=s=320x180:r=30:d=8")
    r = by_name(run_qa(v, expected=8.0))
    assert r["no_black_gaps"] and r["no_frozen_picture"] and r["av_length_match"] and r["narration_length_match"]
    assert not r["resolution"]  # 320x180 is not the 1920x1080 spec


def test_black_gap_is_caught(tmp_path):
    src = "testsrc2=s=320x180:r=30:d=8,drawbox=enable='between(t,3,5)':c=black:t=fill"
    assert not by_name(run_qa(make(tmp_path / "black.mp4", src)))["no_black_gaps"]


def test_frozen_picture_is_caught(tmp_path):
    src = "testsrc2=s=320x180:r=30:d=10,trim=end_frame=1,loop=loop=299:size=1,setpts=N/30/TB"
    assert not by_name(run_qa(make(tmp_path / "freeze.mp4", src, dur=10)))["no_frozen_picture"]


def test_length_mismatch_is_caught(tmp_path):
    v = make(tmp_path / "short.mp4", "testsrc2=s=320x180:r=30:d=8")
    r = by_name(run_qa(v, expected=12.0, min_duration=480))
    assert not r["narration_length_match"] and not r["min_length"]
