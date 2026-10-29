"""
Write the whole explainer script with Claude, through the Claude Code CLI on the owner's own
subscription (CLAUDE_CODE_OAUTH_TOKEN, a GitHub secret), so there is no per-use API bill.

One call returns the full script (outline + every shot). The usual checks still run on it
afterwards: scene repair, repeat filter, number check against the source, length and rules.
Anything that goes wrong (no token, CLI missing, timeout, bad JSON, too short) returns None,
and the free-model writer takes over, so a run never fails because of this step.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)


def available() -> bool:
    return bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN")) and bool(shutil.which("claude")) and config.CLAUDE_SCRIPTS


def ask(prompt: str, timeout: int = 900) -> str:
    """Claude's answer as text. Runs in an empty folder with no tools, so it can only write."""
    with tempfile.TemporaryDirectory() as cwd:
        r = subprocess.run(
            ["claude", "-p", "--model", config.CLAUDE_SCRIPT_MODEL, "--output-format", "text", "--tools", ""],
            input=prompt, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            env={**os.environ, "DISABLE_AUTOUPDATER": "1"},
        )
    if r.returncode != 0:
        raise RuntimeError(f"claude exited {r.returncode}: {(r.stderr or r.stdout)[-300:]}")
    return r.stdout


def flatten(chapters: List[Dict]) -> List[Dict]:
    """[{title, shots}] → shots, each chapter's first shot marked with its title."""
    shots: List[Dict] = []
    for ch in chapters:
        got = [s for s in (ch.get("shots") or []) if isinstance(s, dict) and str(s.get("text", "")).strip()]
        if got:
            got[0]["chapter"] = str(ch.get("title", ""))[:40]
            shots += got
    return shots
