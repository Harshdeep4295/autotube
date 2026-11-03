import json
from unittest import mock

from agents import claude_writer as C


def test_flatten_marks_chapter_starts_and_drops_empty_shots():
    shots = C.flatten([{"title": "Hook", "shots": [{"text": "a"}, {"text": " "}, {"text": "b"}]},
                       {"title": "End", "shots": [{"text": "c"}]}])
    assert [s["text"] for s in shots] == ["a", "b", "c"]
    assert shots[0]["chapter"] == "Hook" and shots[2]["chapter"] == "End" and "chapter" not in shots[1]


def test_not_available_without_the_token(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    assert not C.available()


def test_claude_failure_falls_back_to_the_free_models(monkeypatch):
    from agents.explainer_script_agent import ExplainerScriptAgent
    agent = ExplainerScriptAgent(llm=mock.Mock())
    agent.kind = "tool"
    monkeypatch.setattr(C, "available", lambda: True)
    monkeypatch.setattr(C, "ask", mock.Mock(side_effect=RuntimeError("timeout")))
    assert agent.with_claude({"topic": "t"}, "src") is None
    monkeypatch.setattr(C, "ask", lambda p: json.dumps({"title": "T", "chapters": [{"title": "c", "shots": [{"text": "too short"}]}]}))
    assert agent.with_claude({"topic": "t"}, "src") is None   # far below the target length


def test_claude_script_is_used_when_long_enough(monkeypatch):
    from agents.explainer_script_agent import ExplainerScriptAgent
    from config import config
    agent = ExplainerScriptAgent(llm=mock.Mock())
    agent.kind = "concept"
    line = "word " * 20
    chapters = [{"title": f"c{i}", "shots": [{"text": line, "scene": {"type": "key_point", "props": {}}}] * 9}
                for i in range(4)]
    seen = {}
    monkeypatch.setattr(C, "available", lambda: True)
    monkeypatch.setattr(C, "ask", lambda p: seen.setdefault("p", p) and json.dumps({"title": "T", "chapters": chapters}))
    got = agent.with_claude({"topic": "MoE"}, "the source")
    assert got and len(got["shots"]) == 36 and got["shots"][0]["chapter"] == "c0"
    assert "the source" in seen["p"] and "HOW-IT-WORKS" in seen["p"] and config.EXPLAINER_TARGET_WORDS


def test_a_short_claude_script_is_lengthened_once(monkeypatch):
    from agents.explainer_script_agent import ExplainerScriptAgent, word_count
    from config import config
    agent = ExplainerScriptAgent(llm=mock.Mock())
    agent.kind = "concept"
    line = "word " * 20
    short = [{"title": f"c{i}", "shots": [{"text": line, "scene": {"type": "key_point", "props": {}}}] * 8} for i in range(4)]
    long_ = [{"title": f"c{i}", "shots": [{"text": line, "scene": {"type": "key_point", "props": {}}}] * 10} for i in range(4)]
    asks = mock.Mock(side_effect=[json.dumps({"title": "T", "chapters": short}),
                                  json.dumps({"title": "T", "chapters": long_})])
    monkeypatch.setattr(C, "available", lambda: True)
    monkeypatch.setattr(C, "ask", asks)
    monkeypatch.setattr(config, "CLAUDE_TARGET_WORDS", 760)
    monkeypatch.setattr(config, "CLAUDE_MIN_WORDS", 680)
    got = agent.with_claude({"topic": "MoE"}, "src")
    assert asks.call_count == 2 and word_count(got["shots"]) == 800
    assert "640 words" in asks.call_args_list[1][0][0]
    # a failed second call keeps the first script (640 words is still above 75% of the target)
    asks2 = mock.Mock(side_effect=[json.dumps({"title": "T", "chapters": short}), RuntimeError("timeout")])
    monkeypatch.setattr(C, "ask", asks2)
    assert word_count(agent.with_claude({"topic": "MoE"}, "src")["shots"]) == 640
