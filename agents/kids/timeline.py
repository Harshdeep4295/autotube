"""Voiced lines → timeline: absolute line/word times and per-scene beat times (seconds from scene start)."""

from typing import Dict, List

from agents.kids_scene_schema import CATALOGUE
from agents.word_timing import norm

LEAD_S = 0.5      # silence before the first line
LINE_GAP_S = 0.35  # pause after each line
SCENE_GAP_S = 0.7  # extra pause when a scene ends
TAIL_S = 1.4      # hold the last frame


def n_beats(scene: Dict) -> int:
    if scene["type"] == "trade":
        return 1 + len(scene["props"].get("buyers") or [])
    return len(CATALOGUE[scene["type"]]["beats"])


def cue_time(words: List, cue: str) -> float:
    """Start time (relative to line start) of the first word of `cue` in the line; 0 if not found."""
    target = [norm(w) for w in cue.split() if norm(w)]
    toks = [norm(w) for w, _, _ in words]
    if not target:
        return 0.0
    for i in range(len(toks) - len(target) + 1):
        if toks[i:i + len(target)] == target:
            return words[i][1]
    for i, tk in enumerate(toks):  # partial: first word only
        if tk == target[0]:
            return words[i][1]
    return 0.0


def build(script: Dict, voiced: List[List[Dict]]) -> Dict:
    """
    script: validated kids script. voiced[s][l] = {"dur": audio seconds, "speech": seconds of speech,
    "words": [(word, start, end)] relative to the line start}.
    Returns {"duration", "scenes": [{type, props, weather, start, end, beats, lines: [...]}]} and the
    per-line gap plan used to assemble the audio ("gaps": [[gap_after_line, ...], ...]).
    """
    t = LEAD_S
    scenes, gaps = [], []
    for sc, lines in zip(script["scenes"], voiced):
        start = t
        out_lines, g = [], []
        for i, (ln, v) in enumerate(zip(sc["lines"], lines)):
            gap = LINE_GAP_S + (SCENE_GAP_S if i == len(lines) - 1 else 0.0)
            out_lines.append({"text": ln["text"], "cue": ln.get("cue", ""), "start": round(t, 3),
                              "dur": round(v["speech"], 3),
                              "words": [(w, round(t + a, 3), round(t + b, 3)) for w, a, b in v["words"]]})
            t += v["dur"] + gap
            g.append(gap)
        gaps.append(g)
        nb = n_beats(sc)
        beats = []
        nl = len(out_lines)
        for k in range(nb):
            if k < nl:
                ln = out_lines[k]
                rel = ln["start"] - start
                if ln["cue"]:
                    rel += max(0.0, cue_time([(w, a - ln["start"], b) for w, a, b in ln["words"]], ln["cue"]) - 0.1)
                beats.append(round(rel, 3))
            else:  # more beats than lines: spread the rest over what is left of the last line
                last = out_lines[-1]
                base = max(beats[-1], last["start"] - start)
                end = max(last["start"] - start + last["dur"], base + 0.6 * (nb - nl))
                frac = (k - nl + 1) / (nb - nl + 1)
                beats.append(round(base + (end - base) * frac, 3))
        scenes.append({"type": sc["type"], "props": sc["props"], "weather": sc.get("weather", "sunny"),
                       "start": round(start, 3), "end": round(t, 3), "beats": beats, "lines": out_lines})
    duration = t + TAIL_S
    scenes[-1]["end"] = round(duration, 3)
    return {"duration": round(duration, 3), "scenes": scenes, "gaps": gaps,
            "backdrop": script.get("backdrop", "meadow")}
