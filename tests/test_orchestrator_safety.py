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
    o.voice = mock.Mock()
    o.video = mock.Mock()
    o.thumbnail = mock.Mock()
    o.research = mock.Mock()
    o.uploader = mock.Mock()
    o._get_uploader = mock.Mock(return_value=o.uploader)
    o._update_pending_status = mock.Mock()
    o._log_to_firestore = mock.Mock()
    o._print_summary = mock.Mock()
    o._save_report = mock.Mock()
    return o


ROW = {"id": 7, "topic": "Local AI", "script_json": {"title": "T"}}


def test_queued_script_dry_run_never_uploads_or_touches_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    o = bare(dry_run=True)
    res = o._process_pending_scripts([ROW])
    assert res[0]["success"]
    o._get_uploader.assert_not_called()
    o._update_pending_status.assert_not_called()


def test_queued_script_failed_upload_is_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(orch_mod.config, "OUTPUT_DIR", str(tmp_path))
    o = bare(dry_run=False)
    o.uploader.publish.return_value = {"success": False, "error": "quota"}
    res = o._process_pending_scripts([ROW])
    assert res[0]["success"] is False
    assert o._update_pending_status.call_args_list[-1].args[:2] == (7, "failed")


def _fake_render(video_dir):
    return {"video_path": str(video_dir / "v.mp4"), "thumbnail_path": str(video_dir / "t.jpg"),
            "duration": 500.0, "chapters": [], "report": {}, "script": {}}


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
