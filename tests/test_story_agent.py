"""Tech story of the day: which days, how a story is picked, and how the daily pick and planner use it."""
from datetime import date
from unittest import mock

from agents import story_agent as SA
from config import config

HEADS = [
    {"title": "Intel shares fall 29%", "summary": "Investors sue.", "url": "https://x/1", "source": "bbc", "age": 2},
    {"title": "Rocket failure destroys 40 satellites", "summary": "Vulcan failed.", "url": "https://x/2", "source": "ars", "age": 5},
]


def test_story_days_alternate_from_the_start_date():
    assert not SA.is_story_day(date(2026, 11, 16))
    assert SA.is_story_day(date(2026, 11, 17))
    assert not SA.is_story_day(date(2026, 11, 18))
    assert SA.is_story_day(date(2026, 11, 19))
    with mock.patch.object(config, "EXPLAINER_STORIES", False):
        assert not SA.is_story_day(date(2026, 11, 17))


def _pick(answer, article="x" * 2000, dup=None):
    with mock.patch.object(SA, "headlines", return_value=HEADS), mock.patch.object(SA, "_ask", return_value=answer), \
            mock.patch("agents.source_fetcher.fetch_text", return_value=article), \
            mock.patch("agents.topic_judge.same_as", return_value=dup):
        return SA.pick(["Run Ollama Locally"])


def test_pick_takes_the_first_good_story():
    t = _pick('{"picks": [{"n": 2, "topic": "Rocket failure: why 40 satellites were lost", "why": "big"}]}')
    assert t["kind"] == "story" and t["url"] == "https://x/2" and t["source_url"] == "https://x/2"
    assert t["topic"].startswith("Rocket failure")


def test_pick_skips_unreadable_articles_and_bad_answers():
    assert _pick('{"picks": [{"n": 2, "topic": "t"}]}', article="short") is None
    assert _pick("not json") is None
    assert _pick('{"picks": [{"n": 9, "topic": "t"}]}') is None
    assert _pick('{"picks": [{"n": 2, "topic": "t"}]}', dup=(0.95, "old")) is None


def test_research_takes_the_story_on_a_story_day(tmp_path):
    from agents.research_agent import ResearchAgent
    story = {"topic": "Rocket failure: why 40 satellites were lost", "kind": "story", "source": "story", "url": "u"}
    agent = ResearchAgent()
    with mock.patch.object(SA, "is_story_day", return_value=True), mock.patch.object(SA, "pick", return_value=story), \
            mock.patch.object(config, "EXPLAINER_TRENDS", False), mock.patch.object(agent, "_load_history", return_value=[]), \
            mock.patch("agents.published.channel_titles", return_value=[]):
        assert agent.get_topics(1, record=False) == [story]


def test_no_story_falls_back_to_the_usual_topic():
    from agents.research_agent import ResearchAgent
    agent = ResearchAgent()
    with mock.patch.object(SA, "is_story_day", return_value=True), mock.patch.object(SA, "pick", return_value=None), \
            mock.patch.object(config, "EXPLAINER_TRENDS", False), mock.patch.object(agent, "_load_history", return_value=[]), \
            mock.patch("agents.published.channel_titles", return_value=[]), \
            mock.patch.object(agent, "_from_bank", return_value=[{"topic": "bank one"}]):
        assert agent.get_topics(1, record=False) == [{"topic": "bank one"}]


def test_a_story_slot_in_the_plan_is_not_a_topic():
    from agents.research_agent import ResearchAgent
    with mock.patch("agents.week_plan.for_today", return_value=SA.slot("2026-11-17")):
        assert ResearchAgent()._planned_today([]) is None


def test_story_kind_has_its_prompts():
    from agents.explainer_script_agent import topic_kind
    from templates import explainer_prompts as P
    assert topic_kind({"kind": "story"}) == "story"
    assert "TECH STORY" in P.KIND_NOTES["story"] and P.TITLE_RULES["story"]
    assert "news itself" in P.first_rule("question", "story")
