import json
import subprocess

from scripts.commit_state import merge_lists


def test_merge_keeps_remote_order_and_adds_only_new():
    remote = [{"topic": "a"}, {"topic": "b"}]
    ours = [{"topic": "a"}, {"topic": "c"}]
    assert merge_lists(remote, ours) == [{"topic": "a"}, {"topic": "b"}, {"topic": "c"}]


def test_merge_is_idempotent_and_key_order_insensitive():
    remote = [{"a": 1, "b": 2}]
    assert merge_lists(remote, [{"b": 2, "a": 1}]) == remote


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_survives_a_race_with_another_pusher(tmp_path):
    """Our push is behind origin (another workflow pushed first): both entries must land."""
    import os
    import sys
    from pathlib import Path

    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(origin), str(seed))
    for repo in (seed,):
        _git(repo, "config", "user.email", "t@t"); _git(repo, "config", "user.name", "t")
    (seed / "data").mkdir()
    (seed / "data/posted.json").write_text("[]")
    _git(seed, "add", "."); _git(seed, "commit", "-qm", "seed"); _git(seed, "push", "-q", "origin", "main")

    ours = tmp_path / "ours"
    _git(tmp_path, "clone", "-q", str(origin), str(ours))
    _git(ours, "config", "user.email", "t@t"); _git(ours, "config", "user.name", "t")
    # Another workflow pushes first.
    (seed / "data/posted.json").write_text(json.dumps([{"id": "kids"}]))
    _git(seed, "commit", "-qam", "kids"); _git(seed, "push", "-q", "origin", "main")
    # Our run appended to its (now stale) copy.
    (ours / "data/posted.json").write_text(json.dumps([{"id": "explainer"}]))

    script = Path(__file__).resolve().parent.parent / "scripts" / "commit_state.py"
    res = subprocess.run([sys.executable, str(script), "-m", "state", "data/posted.json"],
                         cwd=ours, capture_output=True, text=True, env={**os.environ})
    assert res.returncode == 0, res.stderr
    _git(seed, "pull", "-q", "origin", "main")
    assert json.loads((seed / "data/posted.json").read_text()) == [{"id": "kids"}, {"id": "explainer"}]
