from agents.explainer_agent import chapters_from, description_with_chapters, fmt_ts, hashtags_for


def shots(marks, total=600):
    out, t = [], 0.0
    step = total / 60
    for i in range(60):
        s = {"start": t, "duration": step}
        if i in marks:
            s["chapter"] = marks[i]
        out.append(s)
        t += step
    return out


def test_chapters_need_three_and_start_at_zero():
    ch = chapters_from(shots({2: "Why", 20: "How", 40: "Next"}))
    assert [c["title"] for c in ch] == ["Intro", "Why", "How", "Next"] and ch[0]["t"] == 0.0
    assert chapters_from(shots({0: "Only", 30: "Two"})) == []


def test_description_has_chapters_sources_and_disclosure():
    d = description_with_chapters("About local AI.", [{"t": 0, "title": "Intro"}, {"t": 75, "title": "How"}],
                                  [{"title": "Ollama", "url": "https://github.com/ollama/ollama"}])
    assert "0:00 Intro" in d and "1:15 How" in d and "https://github.com/ollama/ollama" in d
    assert "AI-generated" in d and fmt_ts(3725) == "1:02:05"


def test_hashtags_name_the_tool():
    assert hashtags_for("Run Kokoro: Free Open-Source Voice Model") == "#Kokoro #LocalAI #OpenSource"
    assert hashtags_for("Understanding llama.cpp: The Engine") == "#LocalAI #OpenSource"      # lower-case name skipped
    assert hashtags_for("Run a ChatGPT-like AI Locally") == "#LocalAI #OpenSource"
    assert hashtags_for("Run LocalAI: Free API") == "#LocalAI #OpenSource"                     # no duplicate
    d = description_with_chapters("About.", [], [], "Run Jan Offline: Open-Source Chat")
    assert d.endswith("#Jan #LocalAI #OpenSource")


def test_hashtag_uses_the_repo_for_multi_word_names():
    cases = [
        ("Run Text Generation WebUI: Power Tool", "oobabooga/text-generation-webui", "#TextGenerationWebUI"),
        ("Run Stable Diffusion WebUI Locally: Free Images", "AUTOMATIC1111/stable-diffusion-webui", "#StableDiffusionWebUI"),
        ("Install Open WebUI: ChatGPT-Style UI", "open-webui/open-webui", "#OpenWebUI"),
        ("Run llama.cpp: The Engine", "ggml-org/llama.cpp", "#llamacpp"),
        ("How to Run Hugging Face Transformers", "huggingface/transformers", "#Transformers"),
        ("Free AI Images with ComfyUI", "comfyanonymous/ComfyUI", "#ComfyUI"),
        ("Run LocalAI: Free API", "mudler/LocalAI", ""),
    ]
    for title, repo, tag in cases:
        assert hashtags_for(title, repo) == " ".join(x for x in (tag, "#LocalAI #OpenSource") if x), title
    assert hashtags_for("How to Run Llama 3 on Your PC") == "#LocalAI #OpenSource"            # no '#How'
    assert hashtags_for("Free Speech-to-Text with Whisper") == "#LocalAI #OpenSource"        # no '#Free'


def test_hashtags_survive_the_length_cut():
    d = description_with_chapters("x" * 6000, [], [], "Run Jan: Chat", "janhq/jan")
    assert len(d) <= 4900 and d.endswith("#Jan #LocalAI #OpenSource")
