"""The same-video check: hard line, AI judge in the grey zone, and its use in the pickers."""
from unittest import mock

import pytest

from agents import topic_judge
from config import config

PAST = ["Why do things cost more?", "Why do house prices change?", "How does AI learn?"]


def scores(table):
    """A fake topic_index.similar: fixed scores per past topic."""
    def similar(text, others, k=3):
        got = sorted(((table.get(o, 0.1), o) for o in others), reverse=True)
        return got[:k]
    return similar


@pytest.fixture
def judge_on():
    topic_judge.reset()
    with mock.patch.object(config, "TOPIC_JUDGE", True):
        yield
    topic_judge.reset()


def test_above_the_hard_line_is_a_repeat_without_asking(judge_on):
    with mock.patch.object(topic_judge.topic_index, "similar", scores({"How does AI learn?": 0.9})), \
            mock.patch.object(topic_judge, "_ask") as ask:
        assert topic_judge.same_as("How does AI get smarter?", PAST, "kids") == (0.9, "How does AI learn?")
        ask.assert_not_called()


def test_grey_zone_asks_the_judge(judge_on):
    table = {"Why do things cost more?": 0.77, "Why do house prices change?": 0.79}
    with mock.patch.object(topic_judge.topic_index, "similar", scores(table)), \
            mock.patch.object(topic_judge, "_ask", return_value='{"same": 2, "why": "same idea"}') as ask:
        # closest first: 1 = house prices (0.79), 2 = things cost more (0.77)
        assert topic_judge.same_as("Why do prices jump up?", PAST, "kids") == (0.77, "Why do things cost more?")
        prompt = ask.call_args[0][0]
        assert "1. Why do house prices change?" in prompt and "2. Why do things cost more?" in prompt
        assert "3. " not in prompt                          # below the grey zone: not shown


def test_judge_says_different(judge_on):
    with mock.patch.object(topic_judge.topic_index, "similar", scores({"Why do house prices change?": 0.79})), \
            mock.patch.object(topic_judge, "_ask", return_value='{"same": 0}'):
        assert topic_judge.same_as("Why does gasoline cost so much?", PAST, "kids") is None


@pytest.mark.parametrize("answer", [None, "no json", '{"same": 9}', '{"same": "x"}'])
def test_no_usable_answer_is_not_a_repeat(judge_on, answer):
    with mock.patch.object(topic_judge.topic_index, "similar", scores({"Why do things cost more?": 0.77})), \
            mock.patch.object(topic_judge, "_ask", return_value=answer):
        assert topic_judge.same_as("Why do prices jump up?", PAST, "kids") is None


def test_low_score_and_judge_off_skip_the_judge(judge_on):
    with mock.patch.object(topic_judge.topic_index, "similar", scores({"Why do things cost more?": 0.5})), \
            mock.patch.object(topic_judge, "_ask") as ask:
        assert topic_judge.same_as("What is a bank?", PAST, "kids") is None
        ask.assert_not_called()
    with mock.patch.object(config, "TOPIC_JUDGE", False), \
            mock.patch.object(topic_judge.topic_index, "similar", scores({"Why do things cost more?": 0.77})), \
            mock.patch.object(topic_judge, "_ask") as ask:
        assert topic_judge.same_as("Why do prices jump up?", PAST, "kids") is None
        ask.assert_not_called()


def test_explainer_uses_its_own_lines(judge_on):
    # 0.86 is a repeat for kids (>= 0.85) but only the grey zone for explainers (< 0.93)
    with mock.patch.object(topic_judge.topic_index, "similar", scores({"Quantization: big models on small GPUs": 0.86})), \
            mock.patch.object(topic_judge, "_ask", return_value='{"same": 1}') as ask:
        hit = topic_judge.same_as("How quantization shrinks a model", ["Quantization: big models on small GPUs"], "explainer")
        assert hit[1] == "Quantization: big models on small GPUs"
        assert "one explainer per tool" in ask.call_args[0][0]


def test_answers_are_cached(judge_on):
    with mock.patch.object(topic_judge.topic_index, "similar", scores({"Why do things cost more?": 0.77})), \
            mock.patch.object(topic_judge, "_ask", return_value='{"same": 1}') as ask:
        topic_judge.same_as("Why do prices jump up?", PAST, "kids")
        topic_judge.same_as("Why do prices jump up?", PAST, "kids")
        assert ask.call_count == 1


def test_kids_picker_skips_a_feed_idea_the_judge_calls_a_repeat(judge_on, tmp_path):
    from agents import kids_topic_agent as K
    agent = K.KidsTopicAgent(llm=mock.Mock())
    ideas = [{"topic": "Why do prices jump up?", "area": "finance", "source": "feed"},
             {"topic": "Why do shops have sales?", "area": "finance", "source": "feed"}]
    table = {"Why do things cost more?": 0.77}
    with mock.patch.object(agent, "history", return_value=[{"topic": t} for t in ["a?", "b?", "c?"]]), \
            mock.patch.object(agent, "next_area", return_value="finance"), \
            mock.patch.object(agent, "headlines", return_value=["Prices rise"]), \
            mock.patch.object(agent, "ideas_from_headlines", return_value=ideas) as gen, \
            mock.patch("agents.published.channel_titles", return_value=["Why do things cost more? (Explained Like You're 5)"]), \
            mock.patch.object(topic_judge.topic_index, "similar", scores(table)), \
            mock.patch.object(topic_judge, "_ask", side_effect=lambda p: '{"same": 1}' if "NEW topic: Why do prices jump" in p else '{"same": 0}'):
        picks = agent.get_topics(1, mode="feed")
    assert [p["topic"] for p in picks] == ["Why do shops have sales?"]
    # the idea writer was shown the old channel question, not only the bot's own history
    assert "Why do things cost more?" in gen.call_args[0][1]


def test_explainer_bank_skips_a_judged_repeat(judge_on, tmp_path):
    import json
    from agents.research_agent import ResearchAgent
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps({"topics": [
        {"topic": "Quantization explained: small GPUs, big models", "kind": "concept", "url": "u", "source_url": "s"},
        {"topic": "LM Studio: a desktop app for local models", "repo": "lmstudio-ai/lms"}]}))
    table = {"Quantization: How Big AI Models Fit on Small GPUs": 0.86}
    with mock.patch.object(config, "EXPLAINER_TOPICS_FILE", str(bank)), \
            mock.patch("agents.published.channel_titles", return_value=["Quantization: How Big AI Models Fit on Small GPUs"]), \
            mock.patch.object(topic_judge.topic_index, "similar", scores(table)), \
            mock.patch.object(topic_judge, "_ask", side_effect=lambda p: '{"same": 1}' if "NEW topic: Quantization" in p else '{"same": 0}'):
        picks = ResearchAgent()._from_bank(1, [])
    assert picks[0]["topic"].startswith("LM Studio")
