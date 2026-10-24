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
