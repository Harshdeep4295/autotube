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


def test_trend_titles_drop_date_stamps_and_hooks_name_no_other_tool():
    from templates import explainer_prompts as P
    assert T.display_name("deepseek-ai/DeepSeek-V4.1-Flash-1017") == "DeepSeek-V4.1-Flash"
    assert T.display_name("Qwen/Qwen3.8-27B") == "Qwen3.8-27B"
    for style, _ in P.HOOK_STYLES:
        rule = P.first_rule(style, "trend")
        assert "names the new model" in rule and "Ollama" not in rule


def test_model_themes():
    assert T.model_theme(m("baidu/Unlimited-OCR-2", 2, tag="image-text-to-text")) == "ocr"
    assert T.model_theme(m("LiquidAI/LFM3-Omni-2B", 2, tag="any-to-any")) == "omni"
    assert T.model_theme(m("Qwen/Qwen4-Coder-30B", 2)) == "coding"
    assert T.model_theme(m("lab/Some-Encoder", 2, tag="feature-extraction")) == "embedding"   # not coding
    assert T.model_theme(m("deepseek-ai/DeepSeek-V4.1-Flash", 2, tag="image-text-to-text")) == "vision"
    assert T.model_theme(m("LiquidAI/LFM3-1.7B", 2)) == "language"
    # past topics without a stored theme are read from their text
    assert T.theme("MiniCPM-OCR-1.0: the new AI model that reads images and text from openbmb") == "ocr"


def test_same_kind_of_model_is_skipped_for_a_week():
    hist = [{"topic": "Unlimited-OCR-2: the new AI model that reads images and text from baidu, and can you run it at home?",
             "source": "trend", "used_at": "2026-10-27T10:00:00"}]
    models = [m("openbmb/MiniCPM-OCR-1.0", 2, tag="image-text-to-text", score=900), m("Qwen/Qwen4-8B", 2, score=100)]
    with mock.patch.object(config, "TREND_MAX_AGE_DAYS", 14), mock.patch.object(config, "TREND_MIN_LIKES", 250), \
            mock.patch.object(config, "TREND_THEME_DAYS", 7):
        assert [x["id"] for x in T.rank(models, hist, NOW)] == ["Qwen/Qwen4-8B"]
        old = [{**hist[0], "used_at": "2026-10-10T10:00:00"}]
        assert [x["id"] for x in T.rank(models, old, NOW)][0] == "openbmb/MiniCPM-OCR-1.0"
    assert T.to_topic(models[0])["theme"] == "ocr"


def test_trend_days_alternate_with_bank_days():
    from agents.research_agent import ResearchAgent
    r = ResearchAgent.__new__(ResearchAgent)
    after_trend = [{"topic": "Some-OCR-1: the new AI model", "source": "trend", "used_at": "2026-10-28T10:00:00"}]
    after_bank = [{"topic": "Ollama on Windows", "source": "bank", "used_at": "2026-10-28T10:00:00"}]
    small = [m("unknown/Cool-Model", 2, likes=5000), m("Qwen/Qwen4-8B", 2, likes=400)]
    big = small + [m("deepseek-ai/DeepSeek-V5", 1, likes=3000, score=1)]
    fake = mock.Mock(**{"json.return_value": None, "raise_for_status.return_value": None})
    for hist, models, want in ((after_trend, small, "bank"), (after_trend, big, "trend"), (after_bank, small, "trend")):
        fake.json.return_value = models
        with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "bank"), \
                mock.patch.object(config, "EXPLAINER_TRENDS", True), \
                mock.patch.object(config, "TREND_ALTERNATE", True), \
                mock.patch.object(config, "TREND_BIG_LIKES", 1000), \
                mock.patch.object(config, "TREND_MIN_LIKES", 250), \
                mock.patch.object(config, "TREND_MAX_AGE_DAYS", 10_000), \
                mock.patch.object(r, "_load_history", return_value=hist), \
                mock.patch("agents.trend_agent.requests.get", return_value=fake):
            got = r.get_topics(1, record=False)[0]
            assert got["source"] == want, (hist, [x["id"] for x in models])
            if want == "trend" and hist is after_trend:
                assert "DeepSeek-V5" in got["topic"]
