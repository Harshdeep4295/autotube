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


SMALL = {w: i for i, w in enumerate(["zero"] + UNITS)}
SMALL.update({w: 10 + i for i, w in enumerate(TEENS)})
SMALL.update({w: 20 + 10 * i for i, w in enumerate(TENS)})
SCALES = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000, "trillion": 10 ** 12}
NUM_WORD = re.compile(r"[a-z]+", re.I)


def _fmt(v: float) -> str:
    return _norm(f"{v:.6f}") if v != int(v) else str(int(v))


def spelled_numbers(text: str) -> Set[str]:
    """Numbers written as words anywhere ("forty-eight gigabytes", "two hundred fifty-six thousand",
    "forty-two point six"): narration is told to use digits, so a number in words is often a
    rewrite that hid an invented figure from the digit check."""
    out: Set[str] = set()
    words = [w.lower() for w in NUM_WORD.findall((text or "").replace("-", " "))]
    i = 0
    while i < len(words):
        if words[i] not in SMALL:
            i += 1
            continue
        total, cur, j = 0, 0, i
        while j < len(words) and (words[j] in SMALL or words[j] in SCALES or words[j] == "hundred"
                                  or (words[j] == "and" and j + 1 < len(words) and words[j + 1] in SMALL)):
            w = words[j]
            if w in SMALL:
                cur += SMALL[w]
            elif w == "hundred":
                cur = (cur or 1) * 100
            elif w in SCALES:
                total += (cur or 1) * SCALES[w]
                cur = 0
            j += 1
        value = float(total + cur)
        if j + 1 < len(words) and words[j] == "point" and words[j + 1] in SMALL:
            digits = ""
            j += 1
            while j < len(words) and words[j] in SMALL and SMALL[words[j]] < 10:
                digits += str(SMALL[words[j]])
                j += 1
            value = float(f"{int(value)}.{digits}") if digits else value
        out.add(_fmt(value))
        i = max(j, i + 1)
    return out


def numbers_in(text: str) -> Set[str]:
    found = {_norm(m.group()) for m in NUM_RE.finditer(text or "")}
    return found | {_word_value(m) for m in WORD_RE.finditer(text or "")} | spelled_numbers(text)


SCALED = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(k|m|b|thousand|million|billion)\b", re.I)
SCALE_OF = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def source_numbers(text: str) -> Set[str]:
    """Numbers in the source, plus "256K" / "1M" / "8 billion" written out in full."""
    out = numbers_in(text)
    for m in SCALED.finditer(text or ""):
        out.add(_fmt(float(m.group(1).replace(",", "")) * SCALE_OF[m.group(2).lower()]))
    return out


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


# Everyday shell words a README needn't spell out for a command to be real.
SHELL_WORDS = {"sudo", "python", "python3", "pip", "pip3", "install", "-u", "--upgrade", "curl", "wget", "git",
               "clone", "cd", "ls", "npm", "npx", "node", "docker", "run", "uv", "bash", "sh", "chmod", "+x",
               "mkdir", "source", "export", "echo", "cat", "brew", "winget", "apt", "apt-get", "-y", "-m", "-v"}


def command_words(line: str) -> List[str]:
    """The words of a terminal command that must appear in the source: the program, its
    arguments and --flags ("$ ollama pull gpt-oss-20b" -> ollama, pull, gpt-oss-20b). Quoted
    text, JSON bodies and shell syntax are skipped."""
    line = str(line).strip()
    if not line.startswith("$"):
        return []
    toks = line[1:].split()
    out = []
    for t in toks:
        if t in ("sudo", "\\") or t[:1] in ("'", '"', "{", "<", "|", "&", ">") or t.startswith("-d"):
            if t[:1] in ("'", '"', "{"):
                break   # a quoted body follows; its words are content, not a command
            continue
        t = t.split("=")[0] if t.startswith("--") else t
        if re.fullmatch(r"[A-Za-z0-9_.:/@+-]+", t) and len(t) > 1 and t.lower() not in SHELL_WORDS:
            out.append(t)
    return out


def unsupported_numbers(script: Dict, source_text: str) -> List[Dict]:
    """Return [{shot, number, where}] for numbers not found in the source, and for terminal
    commands whose program or --flag the source never shows (where = "command")."""
    allowed = source_numbers(source_text)
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
