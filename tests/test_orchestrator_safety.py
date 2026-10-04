"""Pipeline safety: dry runs never upload; failed uploads are not reported as success;
topics are only recorded after a successful upload."""
import logging
from unittest import mock

import orchestrator as orch_mod
from orchestrator import Orchestrator


def bare(dry_run):
    o = object.__new__(Orchestrator)
    o.dry_run = dry_run
    o.logger = logging.getLogger("test")
    o.research = mock.Mock()
    o.uploader = mock.Mock()
    o._get_uploader = mock.Mock(return_value=o.uploader)
    o._print_summary = mock.Mock()
    o._save_report = mock.Mock()
    return o


def _fake_render(video_dir):
    return {"video_path": str(video_dir / "v.mp4"), "thumbnail_path": str(video_dir / "t.jpg"),
            "duration": 500.0, "chapters": [], "contact_sheet": str(video_dir / "c.jpg"),
            "report": {}, "script": {}}


def test_explainer_dry_run_skips_upload_and_does_not_burn_topic(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    o = bare(dry_run=True)
    script = {"title": "T", "description": "d", "tags": [], "shots": []}
    with mock.patch("agents.explainer_script_agent.ExplainerScriptAgent") as S, \
         mock.patch("agents.explainer_agent.ExplainerAgent") as A:
        S.return_value.generate.return_value = script
        A.return_value.render.side_effect = lambda s, out, min_duration=None: _fake_render(tmp_path)
        res = o._process_explainer({"topic": "Local AI", "url": ""})
    assert res["success"]
    o._get_uploader.assert_not_called()
    o.research.mark_used.assert_not_called()


def test_explainer_topic_recorded_only_after_successful_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    script = {"title": "T", "description": "d", "tags": [], "shots": []}
    for upload_ok in (False, True):
        o = bare(dry_run=False)
        o.uploader.publish.return_value = {"success": upload_ok, "url": "u", "error": "x"}
        with mock.patch("agents.explainer_script_agent.ExplainerScriptAgent") as S, \
             mock.patch("agents.explainer_agent.ExplainerAgent") as A:
            S.return_value.generate.return_value = script
            A.return_value.render.side_effect = lambda s, out, min_duration=None: _fake_render(tmp_path)
            res = o._process_explainer({"topic": "Local AI", "url": ""})
        assert res["success"] is upload_ok
        assert o.research.mark_used.called is upload_ok


def test_kids_dry_run_skips_upload_and_does_not_burn_topic(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    o = bare(dry_run=True)
    topics_agent = mock.Mock()
    script = {"title": "T", "description": "d", "tags": [], "scenes": []}
    with mock.patch("agents.kids_script_agent.KidsScriptAgent") as S, \
         mock.patch("agents.kids_agent.KidsAgent") as A:
        S.return_value.generate.return_value = script
        A.return_value.render.side_effect = lambda s, out, enforce_length=True: _fake_render(tmp_path)
        res = o._process_kids({"topic": "What is interest?"}, topics_agent)
    assert res["success"]
    o._get_uploader.assert_not_called()
    topics_agent.mark_used.assert_not_called()


def test_kids_upload_goes_to_kids_playlist_and_records_topic_only_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(orch_mod.config, "KIDS_PLAYLIST", "Explained Like You're 5")
    script = {"title": "T", "description": "d", "tags": [], "scenes": []}
    for upload_ok in (False, True):
        o = bare(dry_run=False)
        topics_agent = mock.Mock()
        o.uploader.publish.return_value = {"success": upload_ok, "url": "u", "error": "x"}
        with mock.patch("agents.kids_script_agent.KidsScriptAgent") as S, \
             mock.patch("agents.kids_agent.KidsAgent") as A:
            S.return_value.generate.return_value = script
            A.return_value.render.side_effect = lambda s, out, enforce_length=True: _fake_render(tmp_path)
            res = o._process_kids({"topic": "What is interest?"}, topics_agent)
        assert res["success"] is upload_ok
        assert topics_agent.mark_used.called is upload_ok
        assert o.uploader.publish.call_args.kwargs["playlist"] == "Explained Like You're 5"


def test_kids_short_is_uploaded_after_the_full_video_and_cannot_fail_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(orch_mod.config, "KIDS_PUBLISH_AT_UTC", "")
    monkeypatch.setattr(orch_mod.config, "KIDS_SHORT_PUBLISH_AT_UTC", "")
    script = {"title": "What Is a Pension? (Explained Like You're 5)", "description": "d", "tags": ["t"], "scenes": []}

    def render(s, out, enforce_length=True):
        return dict(_fake_render(tmp_path), short_path=str(tmp_path / "short.mp4"))

    for short_ok in (True, False):
        o = bare(dry_run=False)
        o.uploader.publish.side_effect = [{"success": True, "url": "https://youtube.com/watch?v=full"},
                                          {"success": short_ok, "url": "https://youtube.com/watch?v=short", "error": "x"}]
        with mock.patch("agents.kids_script_agent.KidsScriptAgent") as S, \
             mock.patch("agents.kids_agent.KidsAgent") as A:
            S.return_value.generate.return_value = script
            A.return_value.render.side_effect = render
            res = o._process_kids({"topic": "What is a pension?"}, mock.Mock())
        assert res["success"] is True                      # the full video is up either way
        assert res["short"]["success"] is short_ok
        full_call, short_call = o.uploader.publish.call_args_list
        assert short_call.args[0].endswith("short.mp4") and short_call.args[1] is None
        assert short_call.args[2]["title"] == "What Is a Pension? | Explained Like You're 5 #Shorts"
        assert "https://youtube.com/watch?v=full" in short_call.args[2]["description"]
        assert "playlist" not in short_call.kwargs       # the Short stays out of the long-video playlist


def test_kids_dry_run_never_uploads_a_short(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    o = bare(dry_run=True)
    script = {"title": "T", "description": "d", "tags": [], "scenes": []}
    with mock.patch("agents.kids_script_agent.KidsScriptAgent") as S, \
         mock.patch("agents.kids_agent.KidsAgent") as A:
        S.return_value.generate.return_value = script
        A.return_value.render.side_effect = lambda s, out, enforce_length=True: dict(
            _fake_render(tmp_path), short_path=str(tmp_path / "short.mp4"))
        res = o._process_kids({"topic": "What is interest?"}, mock.Mock())
    assert res["success"] and "short" not in res
    o.uploader.publish.assert_not_called()
