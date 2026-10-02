"""
Commit pipeline state files (JSON lists such as topic history / posted videos) back to
main without losing a race with another workflow.

Both daily workflows push to main within minutes of each other; a plain `git push`
is rejected when the other one pushed first (Explainer run #10, 2026-10-02). This:
  1. reads our versions of the files,
  2. fetches the latest branch and resets to it,
  3. writes the union of remote + our entries (no duplicates, remote order first),
  4. commits and pushes; repeats up to --attempts times if the push still loses a race.

    python scripts/commit_state.py -m "chore: update topic history [skip ci]" \
        data/topics_history.json data/posted_videos.json
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List


def merge_lists(remote: List, ours: List) -> List:
    """Remote entries first (in order), then ours that remote doesn't have. Exact-match dedupe."""
    seen = {json.dumps(x, sort_keys=True) for x in remote}
    out = list(remote)
    for item in ours:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()[-500:]}")
    return res


def load_list(text: str, path: str) -> List:
    data = json.loads(text) if text.strip() else []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list")
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--attempts", type=int, default=5)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()

    ours = {}
    for f in a.files:
        p = Path(f)
        if p.exists():
            ours[f] = load_list(p.read_text(), f)
    if not ours:
        print("No state files to commit")
        return 0

    for attempt in range(1, a.attempts + 1):
        git("fetch", "-q", "origin", a.branch)
        git("reset", "-q", "--hard", f"origin/{a.branch}")
        for f, mine in ours.items():
            remote_text = git("show", f"origin/{a.branch}:{f}", check=False)
            remote = load_list(remote_text.stdout, f) if remote_text.returncode == 0 else []
            Path(f).write_text(json.dumps(merge_lists(remote, mine), indent=2, ensure_ascii=False) + "\n")
        git("add", *ours.keys())
        if git("diff", "--staged", "--quiet", check=False).returncode == 0:
            print("Nothing new to commit (already on remote)")
            return 0
        git("commit", "-q", "-m", a.message)
        push = git("push", "-q", "origin", f"HEAD:{a.branch}", check=False)
        if push.returncode == 0:
            print(f"Committed state on attempt {attempt}: {', '.join(ours)}")
            return 0
        print(f"Push rejected (attempt {attempt}/{a.attempts}): {push.stderr.strip()[-200:]}")
        time.sleep(3 * attempt)
    print("Could not push state after retries", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
