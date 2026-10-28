"""
Number check: every specific number in the narration or scenes should appear in
the source text. Anything that doesn't is flagged for the human reviewer (and the
run report) — invented statistics were a core problem of the old channel.

Small structural counts (0-10, e.g. "three steps") are allowed.
"""

import re
from typing import Dict, Iterable, List, Set

NUM_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")
# Spelled-out shares and multipliers ("seventy percent", "thirty-five percent", "twelve times faster"):
# the model writes them out in narration, which the digit pattern alone would miss.
UNITS = "one two three four five six seven eight nine".split()
TEENS = "ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
WORD_RE = re.compile(r"\b(?:(" + "|".join(TENS) + r")(?:[- ](" + "|".join(UNITS) + r"))?|(" + "|".join(TEENS) + r"))"
                     r"\s+(?:percent|per cent|times)\b", re.I)


def _word_value(m: "re.Match") -> str:
    tens, unit, teen = (g.lower() if g else "" for g in m.groups())
    if teen:
        return str(10 + TEENS.index(teen))
    return str(20 + 10 * TENS.index(tens) + (UNITS.index(unit) + 1 if unit else 0))


def _norm(tok: str) -> str:
    t = tok.replace(",", "").replace("$", "").rstrip("%")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def numbers_in(text: str) -> Set[str]:
    found = {_norm(m.group()) for m in NUM_RE.finditer(text or "")}
    return found | {_word_value(m) for m in WORD_RE.finditer(text or "")}


def _scene_numbers(scene: Dict) -> Iterable[str]:
    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            yield _norm(repr(float(v)) if isinstance(v, float) else str(v))
        elif isinstance(v, str):
            yield from numbers_in(v)
        elif isinstance(v, dict):
            for x in v.values():
                yield from walk(x)
        elif isinstance(v, list):
            for x in v:
                yield from walk(x)
    props = dict(scene.get("props", {}))
    props.pop("decimals", None)
    yield from walk(props)


# Scenes whose numbers ARE the picture (bars, dials, a big figure): a made-up "4 GB" here is as
# wrong as a made-up "40 GB", so small numbers get no free pass.
DATA_SCENES = {"big_number", "bar_chart", "line_trend", "meter", "compare"}


def command_words(line: str) -> List[str]:
    """The program name and --flags of a terminal line ("$ ollama run llama3 --verbose")."""
    line = str(line).strip()
    if not line.startswith("$"):
        return []
    toks = line[1:].split()
    if not toks:
        return []
    prog = toks[1] if toks[0] in ("sudo", "python", "python3", "pip", "npx", "uv") and len(toks) > 1 else toks[0]
    return [prog] + [t.split("=")[0] for t in toks if t.startswith("--")]


def unsupported_numbers(script: Dict, source_text: str) -> List[Dict]:
    """Return [{shot, number, where}] for numbers not found in the source, and for terminal
    commands whose program or --flag the source never shows (where = "command")."""
    allowed = numbers_in(source_text)
    src = (source_text or "").lower()
    flags = []
    for i, shot in enumerate(script.get("shots", [])):
        scene = shot.get("scene", {}) or {}
        data = scene.get("type") in DATA_SCENES
        found = [(n, "narration") for n in numbers_in(shot.get("text", ""))]
        found += [(n, "scene") for n in _scene_numbers(scene)]
        for n, where in found:
            try:
                small = float(n) <= 10 and not (data and where == "scene")
            except ValueError:
                small = False
            if not small and n not in allowed:
                flags.append({"shot": i, "number": n, "where": where})
        if src and scene.get("type") == "terminal":
            for line in (scene.get("props") or {}).get("lines", []) or []:
                for w in command_words(line):
                    if w.lower() not in src:
                        flags.append({"shot": i, "number": w, "where": "command"})
    return flags
