"""Variety and accuracy guards added 2026-10-28 (repeats, openings, story shapes, title drift, units)."""
from agents.explainer_script_agent import hook_style_for, is_repeat, tidy_shots
from agents.kids_script_agent import STORY_SHAPES, first_and_last, recent_lines, set_question, story_shape
from agents.scene_schema import validate_and_repair
from templates.explainer_prompts import HOOK_STYLES, first_rule


def test_near_repeated_narration_is_caught_but_different_points_are_not():
    assert is_repeat("Asynchronous weight streaming keeps your GPU compute saturated.",
                     "Asynchronous weight streaming keeps your GPU compute saturated for faster results.")
    assert is_repeat("Load separate VAEs and text encoders to fine-tune memory usage.",
                     "Load separate VAEs and text encoders to offload heavy parts to system RAM.")
    assert not is_repeat("Install Ollama with the Windows installer.",
                         "Pull a model and start chatting in the terminal.")


def test_explainer_openings_take_turns():
    styles = [hook_style_for(n) for n in range(len(HOOK_STYLES) * 2)]
    assert len(set(styles)) == len(HOOK_STYLES)
    assert all(styles[i] != styles[i + 1] for i in range(len(styles) - 1))
    for name, _ in HOOK_STYLES:
        assert "By the end" in first_rule(name)   # named only to forbid it


def test_kids_story_shapes_take_turns():
    assert len({story_shape(n) for n in range(len(STORY_SHAPES))}) == len(STORY_SHAPES)


def test_title_card_says_the_videos_question():
    scenes = [{"type": "title", "props": {"question": "How can computers stop bugs?"},
               "lines": [{"text": "How can computers stop germs?"}, {"text": "Stay and find out."}]},
              {"type": "outro", "lines": [{"text": "Wash your hands today."}]}]
    set_question(scenes, "How can computers stop germs?")
    assert scenes[0]["props"]["question"] == scenes[0]["lines"][0]["text"] == "How can computers stop germs?"
    assert first_and_last(scenes) == ("Stay and find out.", "Wash your hands today.")


def test_recent_lines_are_listed_for_the_writer():
    hist = [{"topic": "a"}, {"topic": "b", "opening": "You will see how a robot helps.", "ending": "Bye!"}]
    assert 'opened: "You will see how a robot helps."' in recent_lines(hist)
    assert recent_lines([{"topic": "a"}]) == "(none recorded yet)"


def test_spelled_out_units_are_shortened_not_cut_off():
    script = {"shots": [{"text": "It needs six gigabytes.", "scene": {"type": "big_number", "props": {
        "value": 6, "unit": "gigabytes", "label": "VRAM", "decimals": "0"}}}]}
    out, _ = validate_and_repair(script)
    assert out["shots"][0]["scene"]["props"]["unit"] == "GB"


def test_payoff_line_survives_the_repeat_filter():
    shots = [{"text": "Install Ollama, pull the gpt-oss model, and chat with it offline.", "chapter": "Setup"},
             {"text": "That is how you run gpt-oss: install Ollama, pull the model, and chat with it offline."},
             {"text": "Which model will you try first?", "scene": {"type": "cta_end"}}]
    assert len(tidy_shots(shots, 0)) == 3


def test_concept_topics_alternate_and_carry_their_source(tmp_path, monkeypatch):
    import json
    from agents.research_agent import ResearchAgent
    from config import config

    monkeypatch.setattr(config, "EXPLAINER_TOPICS_FILE", "data/explainer_topics.json")
    picks = ResearchAgent.__new__(ResearchAgent)._from_bank(2, [])
    kinds = [p["kind"] for p in picks]
    assert set(kinds) <= {"tool", "concept"}
    bank = json.load(open("data/explainer_topics.json"))["topics"]
    for b in bank:
        if b.get("kind") == "concept":
            assert b["source_url"].endswith(".md") and b["url"].startswith("https://")


def test_concept_prompts_name_the_idea_not_a_tool():
    from templates import explainer_prompts as P
    rule = P.first_rule("question", "concept")
    assert "naming the idea" in rule and "naming the tool" not in rule
    user = P.OUTLINE_USER.format(minutes=5, words=700, topic="t", source="s", icons="x",
                                 title_rule=P.TITLE_RULES["concept"], kind_note=P.KIND_NOTES["concept"])
    assert "HOW-IT-WORKS" in user and "Mixture of Experts" in user
