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


def test_caption_hashtags_and_disclaimer_follow_the_topic_area():
    ai = R.caption_for({"title": "How do chatbots talk? (Explained Like You're 5)", "description": "Hi", "area": "ai"})
    assert "#artificialintelligence" in ai and "#financeforbeginners" not in ai
    assert "financial advice" not in ai and "AI-generated" in ai
    money = R.caption_for({"title": "Why do prices rise? (Explained Like You're 5)", "description": "Hi", "area": "finance"})
    assert "#financeforbeginners" in money and "Not financial advice." in money


def _resp(data, status=200):
    r = mock.Mock(status_code=status)
    r.json.return_value = data
    return r


def test_facebook_posts_a_reel_start_upload_finish(tmp_path):
    v = tmp_path / "short.mp4"
    v.write_bytes(b"abc")
    calls = []

    def post(url, **kw):
        calls.append((url, kw.get("data")))
        if url.endswith("/video_reels") and kw["data"]["upload_phase"] == "start":
            return _resp({"video_id": "77", "upload_url": "https://rupload.example/77"})
        return _resp({"success": True})

    with mock.patch.object(R.requests, "get", return_value=_resp({"access_token": "page"})), \
            mock.patch.object(R.requests, "post", side_effect=post):
        assert R.post_facebook(v, "T", "caption", "123", "user") == "77"
    assert [c[0] for c in calls] == ["https://graph.facebook.com/123/video_reels", "https://rupload.example/77",
                                     "https://graph.facebook.com/123/video_reels"]
    assert calls[1][1] == b"abc"
    assert calls[2][1]["video_state"] == "PUBLISHED" and calls[2][1]["description"] == "caption"


def test_facebook_falls_back_to_a_page_video_when_reels_fail(tmp_path):
    v = tmp_path / "short.mp4"
    v.write_bytes(b"abc")

    def post(url, **kw):
        if "video_reels" in url:
            return _resp({"error": {"message": "nope"}}, 400)
        return _resp({"id": "page-video"})

    with mock.patch.object(R.requests, "get", return_value=_resp({"access_token": "page"})), \
            mock.patch.object(R.requests, "post", side_effect=post):
        assert R.post_facebook(v, "T", "caption", "123", "user") == "page-video"
