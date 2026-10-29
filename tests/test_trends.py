from datetime import datetime, timezone
from unittest import mock

from agents import trend_agent as T
from config import config

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def m(id_, days, likes=1000, tag="text-generation", score=100, base=None):
    made = NOW.timestamp() - days * 86400
    return {"id": id_, "createdAt": datetime.fromtimestamp(made, timezone.utc).isoformat().replace("+00:00", "Z"),
            "likes": likes, "trendingScore": score, "pipeline_tag": tag,
            "cardData": {"base_model": base} if base else {}}


def test_family_drops_author_date_and_suffix():
    assert T.family("deepseek-ai/DeepSeek-V4.1-Flash-1017") == "deepseek v41 flash"
    assert T.family("Qwen/Qwen3.8-27B-Instruct") == "qwen38 27b"


def test_copies_old_and_unpopular_models_are_skipped():
    models = [
        m("someone/DeepSeek-V4.1-Flash-GGUF", 2, score=900),
        m("other/DeepSeek-V4.1-Flash-tuned", 2, score=800, base="deepseek-ai/DeepSeek-V4.1-Flash"),
        m("lab/Old-Model", 60, score=700),
        m("lab/Tiny-Fans", 2, likes=10, score=600),
        m("unknown/Cool-Model", 3, score=500),
        m("deepseek-ai/DeepSeek-V4.1-Flash-1017", 10, score=100),
    ]
    with mock.patch.object(config, "TREND_MAX_AGE_DAYS", 14), mock.patch.object(config, "TREND_MIN_LIKES", 250):
        got = [x["id"] for x in T.rank(models, [], NOW)]
    assert got == ["deepseek-ai/DeepSeek-V4.1-Flash-1017", "unknown/Cool-Model"]   # known lab first


def test_a_model_already_covered_is_not_picked_again():
    hist = [{"topic": "DeepSeek-V4.1-Flash-1017: the new AI model ... can you run it at home?"}]
    assert T.covered("deepseek-ai/DeepSeek-V4.1-Flash-1103", hist)
    assert not T.covered("deepseek-ai/DeepSeek-V5", hist)


def test_trend_topic_beats_the_bank_and_falls_back_when_empty(tmp_path):
    from agents.research_agent import ResearchAgent
    r = ResearchAgent.__new__(ResearchAgent)
    trend = T.to_topic(m("Qwen/Qwen4-8B", 2))
    assert trend["kind"] == "trend" and trend["source_url"].endswith("/raw/main/README.md")
    with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "bank"), \
            mock.patch.object(config, "EXPLAINER_TRENDS", True), \
            mock.patch.object(r, "_load_history", return_value=[]), \
            mock.patch("agents.trend_agent.trending_topic", return_value=trend):
        assert r.get_topics(1, record=False)[0]["topic"] == trend["topic"]
    with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "bank"), \
            mock.patch.object(config, "EXPLAINER_TRENDS", True), \
            mock.patch.object(r, "_load_history", return_value=[]), \
            mock.patch("agents.trend_agent.trending_topic", return_value=None):
        assert r.get_topics(1, record=False)[0]["source"] == "bank"


def test_trend_prompts():
    from templates import explainer_prompts as P
    assert "Can You Run" in P.TITLE_RULES["trend"] and "NEW-RELEASE" in P.KIND_NOTES["trend"]


def test_front_matter_is_dropped_from_sources():
    from agents.source_fetcher import markdown_to_text
    assert markdown_to_text("---\nlicense: mit\ntags: [a]\n---\n# Model\nText.") == "# Model\nText."
