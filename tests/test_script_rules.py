import json
from pathlib import Path

from agents.explainer_script_agent import tidy_shots
from agents.script_rules import check_script

FIX = Path(__file__).parent / "fixtures"


def test_fixture_follows_every_rule():
    assert check_script(json.loads((FIX / "kids_stock_market.json").read_text())) == []


def test_each_broken_rule_is_named():
    shots = [{"text": "Welcome back to the channel, today we look at a tool."},
             {"text": "Whisper turns speech into text on a normal computer."},
             {"text": "Whisper turns speech into text on a normal computer."},
             {"text": "Subscribe, and tell us in the comments what to cover."}]
    problems = " ".join(check_script({"title": "Run Ollama Locally", "thumbnail_text": "NO CLOUD", "shots": shots}))
    for part in ("never mention what the title promises", "ask no question", "never speak to the viewer",
                 "first 45 seconds", "never said out loud", "asks for 2 things", "said twice"):
        assert part in problems, part

    good = [{"text": "Want to run Whisper on your own PC for free?"}, {"text": "You will transcribe a file by the end."},
            {"text": "Install it with one command and pick a small model."},
            {"text": "That is how you run Whisper locally: install, pick a model, transcribe."},
            {"text": "Which file will you try first? Tell us in the comments."}]
    assert check_script({"title": "Run Whisper Locally: Free Speech-to-Text", "thumbnail_text": "NO CLOUD", "shots": good}) == []


def test_tidy_drops_repeats_and_extra_end_cards_but_keeps_the_length():
    cta = {"type": "cta_end", "props": {}}
    shots = [{"text": "one two three four five", "chapter": "A"}, {"text": "six seven eight nine ten"},
             {"text": "Six seven eight nine ten."}, {"text": "what do you think", "scene": cta},
             {"text": "tell us what you think", "scene": cta}]
    out = tidy_shots(shots, min_words=5)
    assert [s["text"] for s in out] == ["one two three four five", "six seven eight nine ten", "tell us what you think"]
    assert tidy_shots(shots, min_words=23) == shots          # nothing may be cut below the minimum length
