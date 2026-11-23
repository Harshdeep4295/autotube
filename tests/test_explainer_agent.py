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


def test_description_has_a_subscribe_link_right_after_the_first_paragraph():
    d = description_with_chapters("What you get.\n\nMore detail.", [], [], "Run Jan: Chat")
    first, second, third = d.split("\n\n")[:3]
    assert first == "What you get." and "sub_confirmation=1" in second and third == "More detail."


def test_the_close_asks_to_subscribe_with_a_reason():
    from agents.explainer_script_agent import add_subscribe_ask
    from agents.script_rules import check_script
    shots = [{"text": "Which tool will you try?", "scene": {"type": "cta_end", "props": {"question": "Which tool?"}}}]
    out = add_subscribe_ask(shots, "tool")[-1]
    assert "subscribe" in out["text"] and "every few days" in out["text"]
    assert out["scene"]["props"]["question"] == "Which tool?" and out["scene"]["props"]["sub"]
    assert "story" in add_subscribe_ask([{"text": "", "scene": {"type": "cta_end"}}], "story")[-1]["text"]
    script = {"title": "", "shots":
              [{"text": f"line {i} you?"} for i in range(30)] + [{"text": "That is how you run it."}, out]}
    assert not [p for p in check_script(script) if "close asks" in p]
