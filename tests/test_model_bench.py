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


def test_llama_build_skips_placeholder_releases(monkeypatch, tmp_path):
    import io, tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        data = b"#!/bin/sh\n"
        info = tarfile.TarInfo("llama-b2/llama-bench"); info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    rels = [{"tag_name": "v1.0.0", "assets": [{"name": "nightly-tag.txt"}]},
            {"tag_name": "b2", "assets": [{"name": "llama-b2-bin-ubuntu-vulkan-x64.tar.gz"},
                                          {"name": "llama-b2-bin-ubuntu-x64.tar.gz", "browser_download_url": "u"}]}]

    class R:
        def __init__(self, j=None, c=b""): self._j, self.content = j, c
        def json(self): return self._j
    monkeypatch.setattr(MB.requests, "get", lambda url, **kw: R(rels) if "api.github" in url else R(c=buf.getvalue()))
    assert MB.llama_bench(tmp_path).name == "llama-bench"


def test_no_gguf_but_huge_is_still_reported(monkeypatch):
    monkeypatch.setattr(MB, "gguf_repos", lambda m: [])
    monkeypatch.setattr(MB, "machine", lambda: {"cores": 4, "ram_gb": 16})
    monkeypatch.setattr(MB, "_get", lambda url, **kw: [{"path": f"model-{i}.safetensors", "lfs": {"size": 50 * GB}}
                                                       for i in range(10)] + [{"path": "config.json", "size": 9}])
    b = MB.run("lab/Huge")
    assert b["no_gguf"] and b["full_gb"] == 500.0
    text = MB.as_source(b)
    assert "500.0 GB" in text and "16 GB" in text and "No compressed" in text


def test_no_gguf_and_small_means_no_test(monkeypatch):
    monkeypatch.setattr(MB, "gguf_repos", lambda m: [])
    monkeypatch.setattr(MB, "machine", lambda: {"cores": 4, "ram_gb": 16})
    monkeypatch.setattr(MB, "_get", lambda url, **kw: [{"path": "model.safetensors", "lfs": {"size": 8 * GB}}])
    assert MB.run("lab/Small") is None


def test_captions_retry_while_youtube_is_not_ready(monkeypatch):
    from agents import upload_agent as UA
    calls = []
    agent = UA.UploadAgent.__new__(UA.UploadAgent)

    def insert(vid, srt, MFU):
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("<HttpError 404 ... video could not be found>")
    monkeypatch.setattr(agent, "_insert_captions", insert, raising=False)
    monkeypatch.setattr(UA, "CAPTION_RETRY_SECONDS", 0)
    agent._upload_captions("vid", "x.srt")
    assert len(calls) == 2
