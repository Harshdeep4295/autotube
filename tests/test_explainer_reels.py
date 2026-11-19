"""Explainer Shorts go to Instagram/Facebook with their own caption (not the kids one)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import post_reels as PR  # noqa: E402


def test_explainer_caption_has_link_tool_tag_and_no_kids_words():
    script = {"title": "OpenCode: Install the Open Source AI Coding Agent",
              "description": "OpenCode is a free coding agent. It runs in your terminal. More text here.\n\nChapters:\n0:00 x",
              "shots": []}
    c = PR.caption_for(script, "https://youtube.com/watch?v=abc")
    assert c.startswith("OpenCode: Install") and "https://youtube.com/watch?v=abc" in c
    assert "#opencode" in c and "#localai" in c
    assert "5" not in c.split("\n")[0] and "explained like you're 5" not in c.lower()
    assert "financial advice" not in c and "Chapters" not in c


def test_kids_caption_is_unchanged():
    script = {"title": "What is a bond? (Explained Like You're 5)", "description": "A bond is a loan.",
              "area": "finance", "scenes": []}
    c = PR.caption_for(script)
    assert c.startswith("What is a bond? — explained like you're 5.") and "Not financial advice" in c


def test_tool_tag_only_for_short_names():
    assert PR.tool_tag("Run Qwen 3.6 Locally with Ollama: Setup") == ""
    assert PR.tool_tag("PrivateGPT: Chat With Your Files") == "#privategpt"
    assert PR.tool_tag("How Three Small Failures Took Down Microsoft 365") == ""
