import os
import stat

import pytest

from agents import explainer_agent as ea


def fake_npx(tmp_path, body):
    exe = tmp_path / "npx"
    exe.write_text("#!/bin/sh\n" + body)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(tmp_path)


def runner(tmp_path):
    agent = ea.ExplainerAgent.__new__(ea.ExplainerAgent)
    agent.dir = tmp_path
    return agent


def test_remotion_progress_is_logged_and_success_returns(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("PATH", fake_npx(tmp_path, 'printf "Rendered 10/100\\rRendered 100/100\\n"; echo "Encoded 100/100"\n')
                       + os.pathsep + os.environ["PATH"])
    monkeypatch.setattr(ea, "PROGRESS_EVERY_S", 0)
    caplog.set_level("INFO")
    runner(tmp_path)._remotion(["render", "x"], timeout=30)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("Rendered 10/100" in m for m in msgs) and any("done in" in m for m in msgs)


def test_remotion_failure_includes_output_tail(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", fake_npx(tmp_path, 'echo "Error: composition not found"; exit 3\n')
                       + os.pathsep + os.environ["PATH"])
    with pytest.raises(RuntimeError, match="composition not found"):
        runner(tmp_path)._remotion(["render", "x"], timeout=30)
