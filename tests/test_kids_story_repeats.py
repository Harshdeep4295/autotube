"""Kids stories must not repeat: lead rotation, recent stories in the plan prompt, a re-plan on a judged repeat."""
import json
from unittest import mock

import pytest

from agents import kids_script_agent as KS
from agents import topic_judge
from config import config
from tests.test_kids import PLAN, FakeLLM


def test_lead_rotates_through_the_whole_cast():
    from agents.kids_scene_schema import CHARACTERS
    hist, leads = [], []
    for _ in range(len(CHARACTERS)):
        lead = KS.pick_lead(hist)
        leads.append(lead)
        hist.append({"topic": "q", "lead": lead})
    assert sorted(leads) == sorted(CHARACTERS)
    assert KS.pick_lead(hist) == leads[0]          # then the one who led longest ago


def test_old_rows_without_a_lead_do_not_block_anyone():
    assert KS.pick_lead([{"topic": "q"}]) == "sam"      # the friends who never led go first


def test_recent_stories_lists_world_shape_and_story():
    hist = [{"topic": "What is a neural network?", "world": "apple tree", "shape": "race",
             "story": "sorting apples / neuron = one friend"}, {"topic": "Old one?"}]
    text = KS.recent_stories(hist)
    assert '"What is a neural network?" | world: apple tree | shape: race | story: sorting apples' in text
    assert '"Old one?" | world: ?' in text


def test_story_text():
    assert KS.story_text("apple tree", [{"real": "AI", "kid": "robot"}], "learns") == "apple tree / AI = robot / learns"


def _history():
    return [{"topic": "What is a neural network?", "world": "apple tree",
             "story": "sorting apples / neuron = one friend who checks one thing"}]


def test_plan_prompt_names_the_lead_and_recent_stories():
    llm = FakeLLM([json.dumps(PLAN)])
    with mock.patch.object(KS, "_history", return_value=_history()), mock.patch.object(config, "TOPIC_JUDGE", False):
        topic = {"topic": "How does the stock market work?"}
        plan = KS.KidsScriptAgent(llm).plan(topic)
    assert "LEAD for this video: Sam" in llm.prompts[0]
    assert "sorting apples / neuron" in llm.prompts[0]
    assert plan["lead"] == "sam" and topic["lead"] == "sam"
    assert topic["story"].startswith("lemonade stand / share = a slice")


def test_a_judged_repeat_is_planned_again():
    again = dict(PLAN, world="toy shop")
    llm = FakeLLM([json.dumps(PLAN), json.dumps(again)])
    topic_judge.reset()
    with mock.patch.object(KS, "_history", return_value=_history()), mock.patch.object(config, "TOPIC_JUDGE", True), \
            mock.patch.object(topic_judge, "_ask", return_value='{"same": 1}'):
        topic = {"topic": "How does the stock market work?"}
        KS.KidsScriptAgent(llm).plan(topic)
    topic_judge.reset()
    assert "YOUR FIRST PLAN REPEATED THIS RECENT STORY: sorting apples" in llm.prompts[1]
    assert topic["story"].startswith("toy shop")


def test_mark_used_keeps_the_story(tmp_path):
    from agents import kids_topic_agent as KT
    path = tmp_path / "h.json"
    path.write_text("[]")
    with mock.patch.object(KT, "REPO", tmp_path), mock.patch.object(config, "KIDS_HISTORY_FILE", "h.json"):
        KT.KidsTopicAgent(llm=mock.Mock()).mark_used([{"topic": "q?", "shape": "race", "lead": "ava", "story": "s"}])
    row = json.loads(path.read_text())[0]
    assert (row["shape"], row["lead"], row["story"]) == ("race", "ava", "s")
