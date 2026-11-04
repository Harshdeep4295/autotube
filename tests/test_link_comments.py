from scripts.channel_admin import track_of
from scripts.link_comments import comment_text, full_video_link, to_comment


def test_full_video_link_is_read_from_the_short_description():
    assert full_video_link("Watch the full video: https://youtube.com/watch?v=abc123\n\nMore") == \
        "https://youtube.com/watch?v=abc123"
    assert full_video_link("No link here #Shorts") == ""
    assert comment_text("https://youtube.com/watch?v=abc123") == "▶ Full video: https://youtube.com/watch?v=abc123"


def test_only_public_shorts_with_a_full_video_link_get_a_comment():
    link = "Watch the full video: https://youtube.com/watch?v=full1"
    videos = [
        {"id": "s1", "title": "Why? | Explained Like You're 5 #Shorts", "description": link, "privacy": "public"},
        {"id": "s2", "title": "Scheduled #Shorts", "description": link, "privacy": "private"},
        {"id": "s3", "title": "Old Short #Shorts", "description": "no link", "privacy": "public"},
        {"id": "f1", "title": "Run Ollama Locally", "description": link, "privacy": "public"},
    ]
    assert [(v["id"], url) for v, url in to_comment(videos)] == [("s1", "https://youtube.com/watch?v=full1")]


def test_track_of_upload_titles():
    assert track_of("How does AI learn? | Explained Like You're 5 #Shorts") == "short"
    assert track_of("How does AI learn? (Explained Like You're 5)") == "kids"
    assert track_of("Run Wan2GP: Free AI Video on Low-VRAM GPUs") == "explainer"


def test_one_failing_video_does_not_stop_the_run(monkeypatch, capsys):
    from unittest import mock
    import sys
    import scripts.link_comments as L
    link = "Watch the full video: https://youtube.com/watch?v=full1"
    videos = [{"id": f"s{i}", "title": f"Short {i} #Shorts", "description": link, "privacy": "public"} for i in range(3)]
    monkeypatch.setattr(L, "channel_uploads", lambda yt: ("me", videos))
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    calls = []

    def check(yt, vid, ch):
        calls.append(vid)
        if vid == "s1":
            raise RuntimeError("HttpError 400: The API server failed to successfully process the request")
        return False
    monkeypatch.setattr(L, "has_channel_comment", check)
    fake_agent = mock.Mock()
    monkeypatch.setitem(sys.modules, "agents.upload_agent", mock.Mock(UploadAgent=lambda: fake_agent))
    monkeypatch.setattr(sys, "argv", ["link_comments.py"])
    L.main()
    out = capsys.readouterr().out
    assert calls.count("s1") == 2                     # retried once
    assert "Commented on s0" in out and "Commented on s2" in out
    assert "posted 2" in out and "could not check 1" in out
