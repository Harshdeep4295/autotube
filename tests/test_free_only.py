import pytest

from config import Config


def test_default_config_is_free_only_and_safe(monkeypatch):
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    monkeypatch.delenv("VIDEO_ANIMATION_MODE", raising=False)
    monkeypatch.delenv("VIDEO_PRIVACY", raising=False)
    c = Config()
    assert c.FREE_ONLY and c.paid_features_in_use() == []
    assert c.VIDEO_PRIVACY == "private" and c.VIDEO_SYNTHETIC_MEDIA
    c.assert_free_only()


@pytest.mark.parametrize("env", [
    {"SCRIPT_MODEL_PROVIDER": "claude"},
    {"SCRIPT_MODEL_PROVIDER": "bedrock"},
    {"VIDEO_ANIMATION_MODE": "veo"},
    {"GCS_BUCKET_NAME": "bucket"},
])
def test_paid_services_are_refused(monkeypatch, env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError, match="FREE_ONLY"):
        Config().assert_free_only()


def test_free_llm_chain_never_includes_claude(monkeypatch):
    from agents import llm as llm_mod

    monkeypatch.setattr(llm_mod.config, "FREE_ONLY", True)
    monkeypatch.setattr(llm_mod.config, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_mod.config, "GEMINI_API_KEY", "g")
    monkeypatch.setattr(llm_mod.config, "GROQ_API_KEY", "q")
    providers = {p for p, _, _ in llm_mod.FreeLLM().chain()}
    assert providers == {"gemini", "groq"}


def test_llm_falls_through_to_next_model(monkeypatch):
    from agents import llm as llm_mod

    calls = []

    class Fake(llm_mod.FreeLLM):
        def chain(self):
            def bad(m, *a):
                calls.append(m)
                raise RuntimeError("404 model not found")

            def good(m, *a):
                calls.append(m)
                return '{"ok": true}'
            return [("gemini", "retired-model", bad), ("groq", "free-model", good)]

    assert Fake().complete("s", "u") == '{"ok": true}'
    assert calls == ["retired-model", "free-model"]


def test_llm_follows_retired_model_successor_and_remembers_it():
    from agents import llm as llm_mod

    calls = []

    def fake(model, *a):
        calls.append(model)
        if model == "gemini-2.5-flash-lite":
            raise RuntimeError("404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model "
                               "models/gemini-2.5-flash-lite is no longer available to new users. Please update "
                               "your code to use models/gemini-3.5-flash-lite for the latest features.'}}")
        if model == "gemini-3.5-flash-lite":
            return '{"ok": 1}'
        raise AssertionError(f"unexpected model {model}")

    class Fake(llm_mod.FreeLLM):
        def chain(self):
            return [("gemini", "gemini-2.5-flash-lite", fake), ("gemini", "gemini-2.5-flash", fake)]

    llm = Fake()
    assert llm.complete("s", "u") == '{"ok": 1}'
    assert calls == ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]
    assert llm.last_model == "gemini:gemini-3.5-flash-lite"
    calls.clear()
    assert llm.complete("s", "u") == '{"ok": 1}'   # next chapter: straight to the working model
    assert calls == ["gemini-3.5-flash-lite"]


def test_default_gemini_models_are_current(monkeypatch):
    monkeypatch.delenv("GEMINI_FREE_MODELS", raising=False)
    assert Config().GEMINI_FREE_MODELS == ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
