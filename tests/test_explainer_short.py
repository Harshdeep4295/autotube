import json
import shutil
import subprocess

import pytest

from agents import explainer_short as ES


def shots(lengths, chapters=()):
    out, t = [], 0.0
    for i, d in enumerate(lengths):
        s = {"start": t, "duration": d}
        if i in chapters:
            s["chapter"] = f"ch{i}"
        out.append(s)
        t += d
    return out


def test_cut_prefers_end_of_hook_chapter():
    # chapter 2 starts at shot 4 → hook ends at 4 × 9 = 36 s
    assert ES.pick_cut(shots([9] * 10, chapters=(0, 4))) == 36


def test_cut_falls_back_to_last_shot_boundary_under_limit():
    # hook too short (10 s) → last boundary ≤ 58 s is 10 + 5 × 9.5 = 57.5
    assert ES.pick_cut(shots([10] + [9.5] * 10, chapters=(0, 1))) == pytest.approx(57.5)
    # hook too long (70 s) → same fallback
    assert ES.pick_cut(shots([10] * 10, chapters=(0, 7))) == 50


def test_cut_none_when_first_shot_too_long():
    assert ES.pick_cut(shots([70, 10])) is None


def test_srt_and_ass():
    srt = "1\n00:00:00,000 --> 00:00:02,500\nHello there\n\n2\n00:01:05,100 --> 00:01:07,000\nLater {line}\n"
    caps = ES.parse_srt(srt)
    assert caps == [(0.0, 2.5, "Hello there"), (65.1, 67.0, "Later {line}")]
    ass = ES.build_ass("Run Ollama Locally: Free AI Models on Your PC", "Run It Local", caps, 30.0)
    assert "Hello there" in ass and "Later" not in ass          # captions after the cut are dropped
    assert "RUN IT LOCAL" in ass and "Full video on the channel" in ass
    assert "PlayResX: 1080" in ass and r"\N" in ass               # title wrapped onto rows
    assert ES._ass_time(65.1) == "0:01:05.10"


def test_short_meta_links_full_video():
    m = ES.short_meta({"title": "Run Jan Offline", "description": "First para.\n\nChapters:\n0:00 Intro",
                       "tags": ["jan"]}, "https://youtube.com/watch?v=x")
    assert m["title"] == "Run Jan Offline #Shorts"
    assert m["description"].startswith("Watch the full video: https://youtube.com/watch?v=x")
    assert "Chapters" not in m["description"] and m["tags"] == ["jan"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_make_short_renders_vertical_video(tmp_path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(tmp_path / "video.mp4")], check=True)
    (tmp_path / "props.json").write_text(json.dumps({"shots": shots([8, 8, 8, 6], chapters=(0, 3))}))
    (tmp_path / "captions.srt").write_text("1\n00:00:01,000 --> 00:00:03,000\nA caption\n")
    r = ES.make_short(str(tmp_path), "A test title", "Run It Local")
    assert r and r["duration"] == 24
    from scripts.qa_video import probe
    v = next(s for s in probe(r["path"])["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert abs(float(v["duration"]) - 24) < 0.2
