from unittest import mock

from agents.research_agent import ResearchAgent
from agents.source_fetcher import markdown_to_text
from config import config


def test_clean_decodes_entities_and_tags():
    assert ResearchAgent._clean("Drones &amp;amp; <b>Robots</b>  here") == "Drones & Robots here"


def test_niche_filter():
    ok = ["Run LLMs locally with Ollama", "New open-weight model from Qwen", "The AI that sees", "GPU prices drop"]
    no = ["Fender pedal review", "WWI shipwreck found", "Said the mayor", "Rainy weekend"]
    assert all(ResearchAgent.matches_niche({"topic": t}) for t in ok)
    assert not any(ResearchAgent.matches_niche({"topic": t}) for t in no)


def test_get_topics_record_false_does_not_write_history():
    r = ResearchAgent()
    fake = [{"topic": "Running a local LLM with Ollama on a laptop", "source": "hackernews", "trend_score": 50,
             "reddit_mentions": 0, "url": "https://example.com/a", "summary": "How to run llm locally"}]
    with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "feed"), \
         mock.patch.object(r, "_load_history", return_value=[]), \
         mock.patch.object(r, "_save_to_history") as save, \
         mock.patch.object(r, "_fetch_reddit", return_value=[]), \
         mock.patch.object(r, "_fetch_rss", return_value=[]), \
         mock.patch.object(r, "_fetch_hackernews", return_value=fake), \
         mock.patch.object(r, "_fetch_devto", return_value=[]), \
         mock.patch.object(r, "_fetch_lobsters", return_value=[]):
        topics = r.get_topics(1, record=False)
    assert topics and topics[0]["url"] == "https://example.com/a"
    save.assert_not_called()


def test_bank_mode_picks_next_unused_topic_with_readme_source():
    r = ResearchAgent()
    with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "bank"), \
         mock.patch.object(r, "_load_history", return_value=[]), \
         mock.patch.object(r, "_save_to_history") as save:
        first = r.get_topics(1, record=False)[0]
    assert first["source"] == "bank" and first["url"].startswith("https://github.com/")
    assert first["source_url"].startswith("https://raw.githubusercontent.com/") and first["source_url"].endswith("README.md")
    save.assert_not_called()
    used = [{"topic": first["topic"], "normalized_topic": r._normalize(first["topic"])}]
    with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "bank"), \
         mock.patch.object(r, "_load_history", return_value=used):
        second = r.get_topics(1, record=False)[0]
    assert second["topic"] != first["topic"]


def test_bank_topics_are_on_niche_and_unique():
    r = ResearchAgent()
    bank = r._from_bank(1000, [])
    assert len(bank) >= 30
    assert len({r._normalize(b["topic"]) for b in bank}) == len(bank)
    assert all(ResearchAgent.matches_niche(b) for b in bank)


def test_markdown_to_text_drops_badges_html_and_link_targets():
    md = '<p align="center"><img src="x.png"></p>\n![badge](https://b/x.svg)\n# Tool\nRun [models](https://x.y) locally.'
    assert markdown_to_text(md) == "# Tool\nRun models locally."
