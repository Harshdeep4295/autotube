"""Model test on new-model days: file choice, the source block, and that a failure never stops a run."""

from agents import model_bench as MB
from agents.explainer_script_agent import ExplainerScriptAgent

GB = 1024 ** 3


def test_choose_takes_q4_when_it_fits_else_the_next_smaller():
    files = [{"path": "m-Q8_0.gguf", "size": 8 * GB, "quant": None},
             {"path": "m-Q4_K_M.gguf", "size": 5 * GB, "quant": "Q4_K_M"},
             {"path": "m-Q2_K.gguf", "size": 3 * GB, "quant": "Q2_K"}]
    assert MB.choose(files, 9 * GB)["quant"] == "Q4_K_M"
    assert MB.choose(files, 4 * GB)["quant"] == "Q2_K"
    assert MB.choose(files, 2 * GB) is None


def test_gguf_files_skips_split_files_and_vision_adapters(monkeypatch):
    tree = [{"path": "m-Q4_K_M.gguf", "lfs": {"size": 5 * GB}},
            {"path": "big/m-Q4_K_M-00001-of-00003.gguf", "lfs": {"size": 40 * GB}},
            {"path": "mmproj-F16.gguf", "lfs": {"size": GB}},
            {"path": "README.md", "size": 100}]
    monkeypatch.setattr(MB, "_get", lambda url, **kw: tree)
    assert [f["path"] for f in MB.gguf_files("x/y")] == ["m-Q4_K_M.gguf"]


def test_gguf_repos_puts_the_lab_and_known_quantizers_first(monkeypatch):
    found = [{"id": "someone/Qwen3-8B-GGUF"}, {"id": "unsloth/Qwen3-8B-GGUF"},
             {"id": "Qwen/Qwen3-8B-GGUF"}, {"id": "x/Other-Model-GGUF"}]
    monkeypatch.setattr(MB, "_get", lambda url, **kw: found)
    assert MB.gguf_repos("Qwen/Qwen3-8B") == ["Qwen/Qwen3-8B-GGUF", "unsloth/Qwen3-8B-GGUF", "someone/Qwen3-8B-GGUF"]


def test_any_failure_means_no_test(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("down")
    monkeypatch.setattr(MB, "gguf_repos", boom)
    assert MB.run("a/b") is None
    assert MB.as_source(None) == ""


def test_source_block_carries_the_measured_numbers():
    text = MB.as_source({"fits": True, "cores": 4, "ram_gb": 16, "quant": "Q4_K_M", "size_gb": 4.7,
                         "repo": "unsloth/X-GGUF", "read_tps": 41.2, "write_tps": 9.3, "peak_gb": 5.1})
    for part in ("MEASURED BY THIS CHANNEL", "4 CPU cores", "16 GB", "Q4_K_M", "41.2", "9.3", "5.1 GB"):
        assert part in text


def test_too_big_is_reported_with_the_file_sizes():
    text = MB.as_source({"fits": False, "cores": 4, "ram_gb": 16, "repo": "u/Big-GGUF",
                         "q4_gb": 120.5, "q4_quant": "Q4_K_M", "smallest_gb": 60.2, "smallest_quant": "IQ2_XS"})
    assert "does not fit" in text and "120.5 GB" in text and "60.2 GB" in text


def test_script_source_starts_with_the_test(monkeypatch):
    monkeypatch.setattr("agents.explainer_script_agent.fetch_text", lambda url, **kw: "model card " * 100)
    topic = {"topic": "X", "url": "https://huggingface.co/a/b",
             "bench": {"fits": True, "cores": 4, "ram_gb": 16, "quant": "Q4_K_M", "size_gb": 1.0,
                       "repo": "a/b-GGUF", "read_tps": 100.0, "write_tps": 20.0, "peak_gb": 1.2}}
    src = ExplainerScriptAgent.source_for(ExplainerScriptAgent.__new__(ExplainerScriptAgent), topic)
    assert src.startswith("MEASURED BY THIS CHANNEL") and "model card" in src


def test_kids_prompts_speak_to_adults():
    from templates import kids_prompts as P
    assert "CURIOUS ADULT" in P.SYSTEM and "5-year-old could" not in P.CONCEPT_USER
    assert "talks down" in P.CHECK_USER
