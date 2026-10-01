from unittest import mock

from agents.research_agent import ResearchAgent


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
    with mock.patch.object(r, "_load_history", return_value=[]), \
         mock.patch.object(r, "_save_to_history") as save, \
         mock.patch.object(r, "_fetch_reddit", return_value=[]), \
         mock.patch.object(r, "_fetch_rss", return_value=[]), \
         mock.patch.object(r, "_fetch_hackernews", return_value=fake), \
         mock.patch.object(r, "_fetch_devto", return_value=[]), \
         mock.patch.object(r, "_fetch_lobsters", return_value=[]):
        topics = r.get_topics(1, record=False)
    assert topics and topics[0]["url"] == "https://example.com/a"
    save.assert_not_called()
