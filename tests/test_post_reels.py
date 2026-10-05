import json
from unittest import mock

from scripts import post_reels as R


def test_caption_has_title_link_disclosure_and_fits_instagram():
    c = R.caption_for({"title": "What Is a Pension? (Explained Like You're 5)", "description": "x" * 3000},
                      "https://youtube.com/watch?v=abc")
    assert c.startswith("What Is a Pension? — explained like you're 5.")
    assert len(c) <= 2200
    short = R.caption_for({"title": "What Is a Pension? (Explained Like You're 5)", "description": "Hi"},
                          "https://youtube.com/watch?v=abc")
    assert "https://youtube.com/watch?v=abc" in short and "AI-generated" in short and "#eli5" in short


def test_dry_run_job_is_never_posted(tmp_path, monkeypatch, capsys):
    (tmp_path / "short.mp4").write_bytes(b"x")
    (tmp_path / "script.json").write_text(json.dumps({"title": "T (Explained Like You're 5)"}))
    (tmp_path / "result.json").write_text(json.dumps({"url": "file:///tmp/video.mp4"}))
    monkeypatch.setenv("META_ACCESS_TOKEN", "t")
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "1")
    monkeypatch.setattr("sys.argv", ["post_reels.py", "--dir", str(tmp_path)])
    with mock.patch.object(R.requests, "post") as post, mock.patch.object(R.requests, "get") as get:
        R.main()
    post.assert_not_called()
    get.assert_not_called()
    assert "not posting" in capsys.readouterr().out
