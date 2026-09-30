from unittest import mock

from agents import upload_agent as ua


def test_upload_declares_not_made_for_kids_and_ai_disclosure(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\0" * 16)
    agent = ua.UploadAgent.__new__(ua.UploadAgent)
    agent.youtube = mock.MagicMock()
    agent.youtube.videos().insert().next_chunk.return_value = (None, {"id": "abc"})
    with mock.patch("googleapiclient.http.MediaFileUpload"):
        assert agent._upload_video(str(video), {"title": "t", "description": "d", "tags": []}, None) == "abc"
    body = agent.youtube.videos().insert.call_args.kwargs["body"]
    assert body["status"]["selfDeclaredMadeForKids"] is False     # writable field; "madeForKids" is ignored
    assert "madeForKids" not in body["status"]
    assert body["status"]["containsSyntheticMedia"] is True
    assert body["status"]["privacyStatus"] == "private"
