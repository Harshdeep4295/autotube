"""Search-first rules: giant models skipped, tools before concepts, adult wording in kids descriptions."""

from agents import trend_agent as T


def test_giant_models_are_skipped_but_big_famous_ones_pass():
    assert not T.runs_at_home({"safetensors": {"total": 1_779_752_648_320}})   # LongCat-2.5
    assert T.runs_at_home({"safetensors": {"total": 763_205_315_794}})        # DeepSeek-V4.1-Flash
    assert T.runs_at_home({"safetensors": {"total": 27_800_000_000}})
    assert T.runs_at_home({})                                                   # size unknown


def test_bank_gives_tools_before_concepts(monkeypatch, tmp_path):
    import json
    from agents import research_agent as RA
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps({"topics": [
        {"topic": "Attention explained: how AI reads", "kind": "concept", "url": "u", "source_url": "u"},
        {"topic": "Docling: turn PDFs into data an AI can read", "url": "https://github.com/a/docling"}]}))
    monkeypatch.setattr(RA.config, "EXPLAINER_TOPICS_FILE", str(bank))
    monkeypatch.setattr("agents.published.channel_titles", lambda: [])
    agent = RA.ResearchAgent.__new__(RA.ResearchAgent)
    picks = agent._from_bank(1, [])
    assert picks[0]["topic"].startswith("Docling")


def test_kids_description_says_key_terms():
    from agents.kids_agent import description_for
    d = description_for({"title": "What is a bond? (Explained Like You're 5)", "description": "A bond is a loan.",
                         "analogy": {"map": [{"real": "bond", "kid": "a promise note"}]}})
    assert "Key terms in this video" in d and "Grown-up" not in d
