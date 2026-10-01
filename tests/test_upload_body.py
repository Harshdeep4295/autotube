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


def test_playlist_is_found_by_exact_title_or_created(monkeypatch):
    agent = ua.UploadAgent.__new__(ua.UploadAgent)
    agent.youtube = mock.MagicMock()
    agent.youtube.playlists().list().execute.return_value = {
        "items": [{"id": "PL_other", "snippet": {"title": "Explained"}},
                  {"id": "PL_kids", "snippet": {"title": "Explained Like You're 5"}}]}
    agent._post_upload("vid1", "Explained Like You're 5")
    body = agent.youtube.playlistItems().insert.call_args.kwargs["body"]
    assert body["snippet"]["playlistId"] == "PL_kids" and body["snippet"]["resourceId"]["videoId"] == "vid1"

    agent.youtube.playlists().list().execute.return_value = {"items": []}
    agent.youtube.playlists().insert().execute.return_value = {"id": "PL_new"}
    agent._post_upload("vid2", "Explained Like You're 5")
    assert agent.youtube.playlistItems().insert.call_args.kwargs["body"]["snippet"]["playlistId"] == "PL_new"

    agent.youtube.playlistItems().insert.reset_mock()
    agent._post_upload("vid3", "")                      # no playlist configured → nothing happens
    agent.youtube.playlistItems().insert.assert_not_called()
