from agents.word_timing import align, caption_pages, emphasis_positions, proportional, srt


def monotonic(times):
    return all(s <= e for s, e in times) and all(a[1] <= b[0] + 1e-9 for a, b in zip(times, times[1:]))


def test_proportional_spans_speech_in_order():
    t = proportional(["a", "bb", "ccc"], 3.0)
    assert monotonic(t) and t[0][0] == 0.05 and abs(t[-1][1] - 3.0) < 0.01


def test_align_uses_recognized_times_when_words_match():
    words = "Run a real model offline".split()
    rec = [("run", 0.1, 0.3), ("a", 0.3, 0.4), ("real", 0.4, 0.7), ("model", 0.7, 1.0), ("offline.", 1.0, 1.5)]
    t = align(words, rec, 1.6)
    assert t[2] == (0.4, 0.7) and monotonic(t)


def test_align_fills_unrecognized_words_between_anchors():
    words = "Ollama is free and quick".split()
    rec = [("ollama", 0.0, 0.5), ("quick", 2.0, 2.4)]
    t = align(words, rec, 2.5)
    assert monotonic(t)
    assert 0.5 <= t[1][0] < t[3][1] <= 2.0 + 1e-6


def test_align_without_recognition_falls_back_to_proportional():
    assert align(["a", "b"], [], 1.0) == proportional(["a", "b"], 1.0)


def test_emphasis_marks_whole_phrases_only():
    words = "Size is measured in billions of parameters, of course".split()
    hits = emphasis_positions(words, ["billions of parameters"])
    assert hits == {4, 5, 6}


def test_caption_pages_are_ordered_and_bounded():
    shots = [{"start": 0.0, "duration": 3.0, "emphasis": ["free"],
              "words": [(w, i * 0.3, i * 0.3 + 0.25) for i, w in enumerate("Ollama is free. It runs on your own laptop today".split())]}]
    pages = caption_pages(shots)
    assert all(p["start"] < p["end"] for p in pages)
    assert all(len(p["words"]) <= 6 for p in pages)
    assert pages[0]["words"][-1]["w"] == "free." and pages[0]["words"][-1]["hi"]
    assert "00:00:00,000 -->" in srt(pages) or "00:00:00," in srt(pages)
