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
