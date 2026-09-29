import json

import pytest

from agents import explainer_script_agent as esa
from agents.explainer_script_agent import ExplainerScriptAgent, parse_json_obj


def test_parse_json_obj_variants():
    assert parse_json_obj('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_obj('Sure! Here it is: {"a": "b } \\" {", "c": [1]} hope that helps') == {"a": 'b } " {', "c": [1]}
    with pytest.raises(ValueError):
        parse_json_obj("no json here")


class ScriptedLLM:
    """Returns queued responses; records prompts."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.last_model = "fake:model"

    def complete(self, system, user, max_tokens=0, temperature=0):
        self.prompts.append(user)
        return self.responses.pop(0)


def line(i):
    return f"This is narration line number {i} with enough words to count properly here."


def chapter(n, first=0, cta=False):
    shots = [{"text": line(first + k), "emphasis": ["narration line"],
              "scene": {"type": "key_point", "props": {"text": f"Point {first + k}"}}} for k in range(n)]
    if cta:
        shots[-1]["scene"] = {"type": "cta_end", "props": {"question": "Which will you try?"}}
    return json.dumps({"shots": shots})


OUTLINE = json.dumps({
    "title": "Run a Real AI Model on Your Laptop", "description": "d", "tags": ["a"],
    "thumbnail_text": "Run AI", "thumbnail_subtext": "free", "thumbnail_icon": "laptop",
    "chapters": [{"title": f"Ch {i}", "goal": "g", "key_points": ["k"], "target_words": 40} for i in range(3)],
})


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(esa, "fetch_text", lambda url: "")
    monkeypatch.setattr(esa.config, "EXPLAINER_TARGET_WORDS", 120)
    monkeypatch.setattr(esa.config, "EXPLAINER_MIN_SECONDS", 0)
    monkeypatch.setattr(esa, "CHAPTER_MIN_SHARE", 0.8)


def test_generate_assembles_chapters_and_marks_chapter_starts():
    llm = ScriptedLLM([OUTLINE, chapter(4), chapter(4, 4), chapter(4, 8, cta=True)])
    script = ExplainerScriptAgent(llm).generate({"topic": "Local LLMs", "url": "https://example.com"})
    assert len(script["shots"]) == 12
    assert [s.get("chapter") for s in script["shots"] if s.get("chapter")] == ["Ch 0", "Ch 1", "Ch 2"]
    assert script["shots"][-1]["scene"]["type"] == "cta_end"
    assert script["sources"][0]["url"] == "https://example.com"
    assert "FIRST chapter" in llm.prompts[1] and "LAST chapter" in llm.prompts[3]


def test_invalid_chapter_json_gets_one_repair_round_trip():
    llm = ScriptedLLM([OUTLINE, "not json at all", chapter(4), chapter(4, 4), chapter(4, 8, cta=True)])
    script = ExplainerScriptAgent(llm).generate({"topic": "Local LLMs"})
    assert len(script["shots"]) == 12
    assert "could not be used" in llm.prompts[2]


def test_too_short_script_is_rejected():
    llm = ScriptedLLM([OUTLINE, chapter(1), chapter(1), chapter(1), chapter(1), chapter(1), chapter(1)])
    with pytest.raises(Exception):
        ExplainerScriptAgent(llm).generate({"topic": "Local LLMs"})


def test_parse_json_obj_accepts_list_shapes():
    assert parse_json_obj('[{"title": "t", "chapters": []}]') == {"title": "t", "chapters": []}
    shots = parse_json_obj('[{"text": "a b"}, {"text": "c d"}]')
    assert shots == {"shots": [{"text": "a b"}, {"text": "c d"}]}


def test_salvage_shots_from_cut_off_answer():
    full = json.loads(chapter(3))["shots"]
    text = json.dumps({"shots": full})
    cut = text[: text.index("narration line number 2") + 10]   # third shot cut mid-string
    assert esa.salvage_shots(cut) == full[:2]


def test_short_chapter_is_topped_up_and_cta_stays_last():
    # last chapter comes back with 2 shots (26 words); the top-up adds 3 more before the CTA
    llm = ScriptedLLM([OUTLINE, chapter(4), chapter(4, 4), chapter(2, 8, cta=True), chapter(3, 20)])
    script = ExplainerScriptAgent(llm).generate({"topic": "Local LLMs"})
    assert len(script["shots"]) == 13
    assert script["shots"][-1]["scene"]["type"] == "cta_end"
    assert "do NOT repeat" in llm.prompts[-1]


def test_script_shorter_than_min_seconds_fails_before_render(monkeypatch):
    monkeypatch.setattr(esa.config, "EXPLAINER_MIN_SECONDS", 480)
    llm = ScriptedLLM([OUTLINE, chapter(4), chapter(4, 4), chapter(4, 8, cta=True)])
    with pytest.raises(RuntimeError, match="script too short"):
        ExplainerScriptAgent(llm).generate({"topic": "Local LLMs"})
