from datetime import datetime, timezone
from unittest import mock

from agents import upload_agent as ua
from orchestrator import next_utc_time


def test_next_utc_time_today_or_tomorrow():
    morning = datetime(2026, 9, 30, 4, 0, tzinfo=timezone.utc)
    assert next_utc_time("18:30", morning) == "2026-09-30T18:30:00.000Z"
    late = datetime(2026, 9, 30, 18, 10, tzinfo=timezone.utc)      # less than 30 min lead → tomorrow
    assert next_utc_time("18:30", late) == "2026-10-01T18:30:00.000Z"


def test_publish_at_schedules_private_upload(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\0" * 16)
    agent = ua.UploadAgent.__new__(ua.UploadAgent)
    agent.youtube = mock.MagicMock()
    agent.youtube.videos().insert().next_chunk.return_value = (None, {"id": "abc"})
    for name in ("_set_thumbnail", "_save_to_log", "_post_upload"):
        setattr(agent, name, mock.MagicMock())
    with mock.patch("googleapiclient.http.MediaFileUpload"):
        res = agent.publish(str(video), "t.jpg", {"title": "t", "description": "d", "tags": []},
                            publish_at="2026-09-30T18:30:00.000Z")
    status = agent.youtube.videos().insert.call_args.kwargs["body"]["status"]
    assert status["publishAt"] == "2026-09-30T18:30:00.000Z" and status["privacyStatus"] == "private"
    assert res["success"] and res["publish_at"] == "2026-09-30T18:30:00.000Z"


def test_a_late_run_does_not_double_book_a_day(tmp_path):
    import json
    from orchestrator import free_slot, short_slot
    posted = tmp_path / "posted.json"
    posted.write_text(json.dumps([
        {"title": "How do credit scores work? (Explained Like You're 5)", "publish_at": "2026-11-25T14:30:00.000Z"},
        {"title": "How do credit scores work? | Explained Like You're 5 #Shorts", "publish_at": "2026-11-26T14:30:00.000Z"},
        {"title": "Run X Locally", "publish_at": "2026-11-25T18:30:00.000Z"}]))
    morning = datetime(2026, 11, 25, 11, 0, tzinfo=timezone.utc)
    assert free_slot("14:30", kids=True, now=morning, path=posted) == "2026-11-26T14:30:00.000Z"
    assert free_slot("18:30", kids=False, now=morning, path=posted) == "2026-11-26T18:30:00.000Z"
    assert free_slot("14:30", kids=True, now=morning, path=tmp_path / "none.json") == "2026-11-25T14:30:00.000Z"
    assert short_slot("14:30", "2026-11-26T14:30:00.000Z", morning) == "2026-11-26T14:30:00.000Z"
    assert short_slot("14:30", None, morning) == "2026-11-25T14:30:00.000Z"
