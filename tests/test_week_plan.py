import json
import re
from datetime import date
from unittest import mock

import numpy as np
import pytest

from agents import topic_index, week_plan
from config import config


class FakeEmbedder:
    """Bag of words: shared words → similar vectors (enough to test the plumbing)."""
    VOCAB = {}

    def embed(self, texts):
        for t in texts:
            v = np.zeros(384, dtype=np.float32)
            for w in re.findall(r"[a-z]+", t.lower()):
                if w in {"what", "is", "a", "the", "how", "does", "do"}:
                    continue
                v[self.VOCAB.setdefault(w, len(self.VOCAB) % 384)] += 1
            yield v


@pytest.fixture
def index(tmp_path):
    topic_index.reset()
    with mock.patch.object(config, "TOPIC_INDEX", True), \
            mock.patch.object(config, "TOPIC_INDEX_FILE", str(tmp_path / "index.npz")), \
            mock.patch.object(topic_index, "_embedder", return_value=FakeEmbedder()):
        yield topic_index
    topic_index.reset()


def test_index_finds_a_repeat_by_meaning_and_saves(index, tmp_path):
    past = ["What is a Chip?", "Why do we pay taxes?"]
    assert index.duplicate_of("What is a chip", past, threshold=0.8)[1] == "What is a Chip?"
    assert index.duplicate_of("Why do house prices change?", past, threshold=0.8) is None
    assert index.save(past) == 4                       # the two plus the two questions checked above
    index.reset()
    index._load_file()
    assert "What is a Chip?" in index._vectors


def test_index_off_or_broken_means_word_rules_only():
    topic_index.reset()
    with mock.patch.object(config, "TOPIC_INDEX", False):
        assert topic_index.duplicate_of("What is a Chip?", ["What is a Chip?"]) is None
    with mock.patch.object(config, "TOPIC_INDEX", True), mock.patch.object(topic_index, "_embedder", return_value=None):
        assert topic_index.duplicate_of("x y", ["x y"]) is None


def test_todays_plan_entry(tmp_path):
    plan = {"days": [{"date": "2026-11-12", "explainer": {"topic": "A"}, "kids": {"topic": "Why?"}}]}
    f = tmp_path / "plan.json"
    f.write_text(json.dumps(plan))
    with mock.patch.object(config, "WEEK_PLAN", True), mock.patch.object(week_plan, "REPO", tmp_path), \
            mock.patch.object(config, "WEEK_PLAN_FILE", "plan.json"):
        assert week_plan.for_today("explainer", "2026-11-12") == {"topic": "A"}
        assert week_plan.for_today("kids", "2026-11-13") is None
    with mock.patch.object(config, "WEEK_PLAN", False):
        assert week_plan.for_today("explainer", "2026-11-12") is None


def test_start_dates():
    from scripts.plan_week import start_date
    wed = date(2026, 11, 11)
    assert start_date("tomorrow", wed) == date(2026, 11, 12)
    assert start_date("next-monday", wed) == date(2026, 11, 16)
    assert start_date("next-monday", date(2026, 11, 16)) == date(2026, 11, 23)
    assert start_date("2026-12-01") == date(2026, 12, 1)


def _ctx(bank, models=(), kids_bank=(), kids_done=(), ex_done=()):
    from scripts.plan_week import Checker
    check = Checker([{"topic": t, "source": "bank"} for t in ex_done], [], [], [], list(kids_done))
    return {"checker": check, "bank": list(bank), "models": list(models), "areas": ["ai", "finance", "tech"],
            "kids_bank": list(kids_bank)}


def test_plan_keeps_good_picks_and_fills_rejected_days_from_the_banks():
    from scripts.plan_week import build_plan
    bank = [{"ref": "bank:0", "topic": "Ollama on Windows: run your first model", "kind": "tool",
             "entry": {"topic": "Ollama on Windows: run your first model", "repo": "ollama/ollama"}},
            {"ref": "bank:1", "topic": "Quantization explained", "kind": "concept",
             "entry": {"topic": "Quantization explained", "kind": "concept", "url": "u", "source_url": "s"}},
            {"ref": "bank:2", "topic": "Run Jan offline", "kind": "tool", "entry": {"topic": "Run Jan offline", "repo": "janhq/jan"}}]
    model = {"id": "Qwen/Qwen4-27B", "pipeline_tag": "text-generation", "likes": 3000, "createdAt": "2026-11-10T00:00:00Z"}
    raw = {"days": [
        {"date": "2026-11-12", "explainer": {"ref": "hf:Qwen/Qwen4-27B", "why": "huge"},
         "kids": {"question": "Why is gold so expensive right now?", "hint": "a toy everyone wants"}},
        {"date": "2026-11-13", "explainer": {"ref": "bank:99"},                     # unknown → bank
         "kids": {"question": "Why do we pay taxes?"}},                             # already made → bank
        {"date": "2026-11-14", "explainer": {"ref": "bank:0"}, "kids": {}}]}
    kids_bank = [{"question": "What is a budget?", "area": "finance"}, {"question": "What is Wi-Fi?", "area": "tech"}]
    with mock.patch("agents.trend_agent.covered", return_value=False):
        days = build_plan(["2026-11-12", "2026-11-13", "2026-11-14"], raw,
                          _ctx(bank, [{"ref": "hf:Qwen/Qwen4-27B", "model": model}], kids_bank,
                               kids_done=["Why do we pay taxes?"]))
    assert days[0]["explainer"]["source"] == "trend" and days[0]["explainer"]["model_id"] == "Qwen/Qwen4-27B"
    assert days[0]["kids"] == {"topic": "Why is gold so expensive right now?", "area": "ai", "source": "plan",
                               "hint": "a toy everyone wants", "why": ""}
    assert days[1]["explainer"]["source"] == "bank" and "rejected" in days[1]["explainer"]["why"]
    assert days[1]["kids"]["topic"] == "What is a budget?"                      # finance day → finance question
    assert days[2]["explainer"]["topic"] != days[1]["explainer"]["topic"]
    assert days[2]["kids"]["topic"] == "What is Wi-Fi?"
    assert len({d["explainer"]["topic"] for d in days}) == 3


def test_plan_rejects_topics_already_made():
    from scripts.plan_week import build_plan
    bank = [{"ref": "bank:0", "topic": "Run Jan offline", "kind": "tool", "entry": {"topic": "Run Jan offline", "repo": "janhq/jan"}},
            {"ref": "bank:1", "topic": "Run Aider in your terminal", "kind": "tool",
             "entry": {"topic": "Run Aider in your terminal", "repo": "Aider-AI/aider"}}]
    raw = {"days": [{"date": "2026-11-12", "explainer": {"ref": "bank:0"}, "kids": {"question": "How does AI learn to work?"}}]}
    days = build_plan(["2026-11-12"], raw, _ctx(bank, ex_done=["Run Jan offline"], kids_done=["How does AI learn?"],
                                                kids_bank=[{"question": "What is a robot?", "area": "ai"}]))
    assert days[0]["explainer"]["topic"] == "Run Aider in your terminal"
    assert days[0]["kids"]["topic"] == "What is a robot?"


def test_daily_explainer_takes_the_plan_unless_a_big_release_lands():
    from agents.research_agent import ResearchAgent
    r = ResearchAgent.__new__(ResearchAgent)
    planned = {"topic": "Quantization explained", "kind": "concept", "source": "bank", "url": "u", "source_url": "s"}
    big = {"topic": "Qwen4: the new AI model", "kind": "trend", "source": "trend"}
    with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "bank"), mock.patch.object(config, "EXPLAINER_TRENDS", True), \
            mock.patch.object(r, "_load_history", return_value=[]), \
            mock.patch("agents.week_plan.for_today", return_value=dict(planned)), \
            mock.patch("agents.published.channel_titles", return_value=[]):
        with mock.patch("agents.trend_agent.trending_topic", return_value=None) as tt:
            assert r.get_topics(1, record=False)[0]["topic"] == "Quantization explained"
            assert tt.call_args.kwargs["big_only"] is True      # only a big release may replace the plan
        with mock.patch("agents.trend_agent.trending_topic", return_value=big):
            assert r.get_topics(1, record=False)[0]["source"] == "trend"
    # a planned topic made in the meantime is skipped
    with mock.patch.object(config, "EXPLAINER_TOPIC_MODE", "bank"), mock.patch.object(config, "EXPLAINER_TRENDS", False), \
            mock.patch.object(r, "_load_history", return_value=[{"topic": "Quantization explained", "source": "bank"}]), \
            mock.patch("agents.week_plan.for_today", return_value=dict(planned)), \
            mock.patch("agents.published.channel_titles", return_value=[]), \
            mock.patch.object(r, "_from_bank", return_value=[{"topic": "Other"}]):
        assert r.get_topics(1, record=False)[0]["topic"] == "Other"


def test_daily_kids_takes_the_plan_unless_it_was_made():
    from agents.kids_topic_agent import KidsTopicAgent
    k = KidsTopicAgent()
    planned = {"topic": "Why is gold so expensive?", "area": "finance", "source": "plan", "hint": "h"}
    with mock.patch.object(k, "history", return_value=[]), \
            mock.patch("agents.published.channel_titles", return_value=[]), \
            mock.patch("agents.week_plan.for_today", return_value=dict(planned)):
        assert k.get_topics(1)[0]["topic"] == "Why is gold so expensive?"
    with mock.patch.object(k, "history", return_value=[{"topic": "Why is gold so expensive?", "area": "finance"}]), \
            mock.patch("agents.published.channel_titles", return_value=[]), \
            mock.patch("agents.week_plan.for_today", return_value=dict(planned)), \
            mock.patch.object(k, "headlines", return_value=[]):
        assert k.get_topics(1, mode="bank")[0]["source"] == "bank"


def test_content_db_records_and_summary():
    from agents import content_db
    videos = [{"id": "a", "title": "What is a Chip? | Explained Like You're 5 #Shorts", "privacy": "public"},
              {"id": "b", "title": "Run Wan2GP: Free AI Video on Low-VRAM GPUs", "privacy": "public"}]
    report = {"youtube": {"data_through": "2026-11-07", "videos": [
        {"id": "b", "views": 708, "avg_seconds": 75, "pct": 14.3, "subs": 2}]}}
    db = content_db.build(videos, report)
    assert [v["subject"] for v in db["videos"]] == ["What is a Chip?", "Run Wan2GP: Free AI Video on Low-VRAM GPUs"]
    assert db["videos"][0]["track"] == "kids" and db["videos"][0]["short"]
    assert content_db.subjects(db, "kids") == ["What is a Chip?"]
    assert "708 views" in content_db.summary(db)
