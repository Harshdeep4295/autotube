"""Kids track ("Explained Like You're 5"): schema, timeline, renderer smoke, script + topic agents (no network)."""

import json
from pathlib import Path

import cairo
import pytest

from agents.kids import props as kprops
from agents.kids import timeline as TLB
from agents.kids.scenes import SCENES
from agents.kids_scene_schema import CATALOGUE, CHARACTERS, PROPS, validate_and_repair, word_count
from agents.kids.cast import CAST

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


# ── schema ────────────────────────────────────────────────────────────────────
def test_catalogue_and_renderer_in_sync():
    assert set(CATALOGUE) == set(SCENES)
    assert set(PROPS) == set(kprops.NAMES)
    assert set(CHARACTERS) == set(CAST)


@pytest.mark.parametrize("name", list(CATALOGUE))
def test_every_example_validates_clean(name):
    spec = CATALOGUE[name]
    hi = 1 + len(spec["example"]["buyers"]) if name == "trade" else spec["lines"][1]
    lines = [{"text": f"line {i} words here"} for i in range(hi)]
    sc = {"type": name, "props": spec["example"], "lines": lines}
    script = {"scenes": [sc, {"type": "outro", "props": {"cast": ["mia"]}, "lines": ["Bye!"]}]}
    safe, repairs = validate_and_repair(script)
    assert safe["scenes"][0]["type"] == name
    assert not [r for r in repairs if r.startswith("scene 0")], repairs


def test_repairs_bad_llm_output():
    script = {"scenes": [
        {"type": "title", "props": {"question": "Why is the sky blue?"}, "lines": ["Hi friend!"]},
        {"type": "laser_show", "lines": [{"text": "Pew pew lasers everywhere"}]},
        {"type": "meet", "props": {"who": "gandalf", "place": "castle"}, "lines": [{"text": "This is Mia.", "cue": "banana"}]},
        {"type": "reveal", "props": {"word": "SKY"}, "lines": ["One.", "Two.", "Three.", "Four."]},
        {"type": "split", "props": {"piece_name": "1 PART", "pieces": 99}, "lines": ["Cut it."]},
        {"type": "trade", "props": {"buyers": []}, "lines": ["Buy it."]},
        {"lines": []},
    ]}
    safe, repairs = validate_and_repair(script)
    types = [s["type"] for s in safe["scenes"]]
    assert types == ["title", "talk", "meet", "reveal", "split", "talk", "outro"]
    meet = safe["scenes"][2]
    assert meet["props"]["who"] == "mia" and meet["props"]["place"] == "stand"
    assert "cue" not in meet["lines"][0]
    assert len(safe["scenes"][3]["lines"]) == 2 and "Four." in safe["scenes"][3]["lines"][1]["text"]
    assert safe["scenes"][4]["props"]["pieces"] == 12
    assert any("added an 'outro'" in r for r in repairs)


def test_no_narration_raises():
    with pytest.raises(ValueError):
        validate_and_repair({"scenes": [{"type": "title", "lines": []}]})


@pytest.mark.parametrize("fixture", ["kids_stock_market.json", "kids_internet.json"])
def test_fixtures_are_valid_and_short(fixture):
    safe, repairs = validate_and_repair(load(fixture))
    assert not repairs, repairs
    assert 150 <= word_count(safe) <= 380  # ≈ 1.5-3 minutes


# ── timeline ─────────────────────────────────────────────────────────────────
def fake_voiced(script, speech=2.0):
    out = []
    for sc in script["scenes"]:
        row = []
        for ln in sc["lines"]:
            words = ln["text"].split()
            step = speech / len(words)
            row.append({"dur": speech, "speech": speech,
                        "words": [(w, i * step, (i + 1) * step) for i, w in enumerate(words)]})
        out.append(row)
    return out


def test_timeline_beats_follow_lines_and_cues():
    safe, _ = validate_and_repair(load("kids_stock_market.json"))
    TL = TLB.build(safe, fake_voiced(safe))
    assert TL["scenes"][0]["start"] == TLB.LEAD_S
    for sc in TL["scenes"]:
        assert len(sc["beats"]) == TLB.n_beats({"type": sc["type"], "props": sc["props"]})
        assert sc["beats"] == sorted(sc["beats"])
        assert sc["end"] > sc["start"]
    price = next(s for s in TL["scenes"] if s["type"] == "price")
    # "Now it costs three!" with cue "three" → beat 1 fires on the 4th word, not the line start
    line1_rel = price["lines"][1]["start"] - price["start"]
    assert price["beats"][1] > line1_rel + 1.0
    starts = [s["start"] for s in TL["scenes"]]
    assert starts == sorted(starts)
    assert TL["duration"] > TL["scenes"][-1]["lines"][-1]["start"]


def test_cue_time_multiword():
    words = [("This", 0.0, 0.2), ("is", 0.2, 0.4), ("the", 0.4, 0.6), ("stock", 0.6, 0.9), ("market!", 0.9, 1.3)]
    assert TLB.cue_time(words, "the stock") == 0.4
    assert TLB.cue_time(words, "market") == 0.9
    assert TLB.cue_time(words, "nope") == 0.0


# ── renderer smoke: every scene, every beat, never raises ────────────────────
@pytest.mark.parametrize("name", list(CATALOGUE))
def test_scene_renders_at_every_beat(name):
    from agents.kids import draw as D

    D.ensure_fonts()
    spec = CATALOGUE[name]
    safe, _ = validate_and_repair({"scenes": [{"type": name, "props": spec["example"],
                                               "lines": [f"Line {i} is here" for i in range(spec["lines"][1])]}]})
    sc = safe["scenes"][0]
    TL = TLB.build({"scenes": [sc]}, fake_voiced({"scenes": [sc]}))
    s = TL["scenes"][0]
    S = {"props": s["props"], "beats": s["beats"], "dur": s["end"] - s["start"], "weather": s["weather"]}
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 480, 270)
    c = cairo.Context(surf)
    c.scale(0.25, 0.25)
    for t in [0.0, 0.3] + [b + d for b in s["beats"] for d in (0.05, 0.6)] + [S["dur"] - 0.1]:
        c.save()
        D.background(c, t, s["weather"])
        SCENES[name](c, t, S)
        c.restore()


def test_every_prop_draws():
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 200, 200)
    c = cairo.Context(surf)
    for n in PROPS:
        kprops.prop(c, n, 100, 100, 150, 1.0)


# ── script agent (fake LLM) ──────────────────────────────────────────────────
class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []
        self.last_model = "fake:model"

    def complete(self, system, user, max_tokens=0, temperature=0.0):
        self.prompts.append(user)
        return self.answers.pop(0)


PLAN = {"question": "How does the stock market work?", "world": "lemonade stand",
        "map": [{"real": "share", "kid": "a slice"}], "story": ["a", "b", "c", "d"], "takeaway": "x"}


def test_script_agent_happy_path():
    from agents.kids_script_agent import KidsScriptAgent

    fx = load("kids_stock_market.json")
    body = {k: fx[k] for k in ("scenes",)}
    body.update({"title": "Stock market", "tags": ["stocks"], "description": "d"})
    llm = FakeLLM(["```json\n" + json.dumps(PLAN) + "\n```", json.dumps(body), json.dumps({"ok": True, "problems": []})])
    s = KidsScriptAgent(llm).generate({"topic": "How does the stock market work?"})
    assert s["title"].endswith("(Explained Like You're 5)")
    assert s["tags"][0] == "Explained Like You're 5"
    assert s["analogy"]["world"] == "lemonade stand"
    assert s["review"]["ok"] is True
    assert 90 <= s["estimated_seconds"] <= 180
    assert "CATALOGUE" in llm.prompts[1] or "beats" in llm.prompts[1]


def test_script_agent_fix_round_and_too_long():
    from agents.kids_script_agent import KidsScriptAgent

    fx = load("kids_stock_market.json")
    body = {"scenes": fx["scenes"], "title": "t", "tags": [], "description": ""}
    llm = FakeLLM([json.dumps(PLAN), json.dumps(body),
                   json.dumps({"ok": False, "problems": ["line 3 gives advice"]}), json.dumps(body)])
    s = KidsScriptAgent(llm).generate({"topic": "q"})
    assert s["review"]["fixed"] is True and s["review"]["problems"] == ["line 3 gives advice"]

    long = {"scenes": fx["scenes"] * 3, "title": "t"}
    llm = FakeLLM([json.dumps(PLAN), json.dumps(long), json.dumps(long), json.dumps(long),
                   json.dumps({"ok": True, "problems": []})])
    with pytest.raises(RuntimeError, match="too long"):
        KidsScriptAgent(llm).generate({"topic": "q"})


# ── topic agent ──────────────────────────────────────────────────────────────
def test_topic_agent_bank_alternates_and_records(tmp_path, monkeypatch):
    from agents import kids_topic_agent as KT
    from config import config

    hist = tmp_path / "hist.json"
    hist.write_text("[]")
    monkeypatch.setattr(config, "KIDS_HISTORY_FILE", str(hist))
    agent = KT.KidsTopicAgent(llm=FakeLLM([]))
    first = agent.get_topics(1, mode="bank")[0]
    assert first["source"] == "bank" and first["area"] == "finance"
    agent.mark_used([first])
    second = agent.get_topics(1, mode="bank")[0]
    assert second["area"] == "tech" and second["topic"] != first["topic"]
    assert json.loads(hist.read_text())[0]["topic"] == first["topic"]


def test_topic_agent_headline_ideas(tmp_path, monkeypatch):
    from agents import kids_topic_agent as KT
    from config import config

    monkeypatch.setattr(config, "KIDS_HISTORY_FILE", str(tmp_path / "h.json"))
    ideas = {"ideas": [{"question": "What is interest?", "area": "finance", "why": "rate cut"},
                       {"question": "Why did the war start?", "area": "finance", "why": "x"}]}
    agent = KT.KidsTopicAgent(llm=FakeLLM([json.dumps(ideas)]))
    monkeypatch.setattr(agent, "headlines", lambda: ["Central bank cuts rates"])
    got = agent.get_topics(2, mode="mixed")
    assert got[0]["topic"] == "What is interest?" and got[0]["source"] == "feed"
    assert got[1]["source"] == "bank"          # blocked idea dropped, bank fills the gap
