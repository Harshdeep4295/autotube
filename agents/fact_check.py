"""
Number check: every specific number in the narration or scenes should appear in
the source text. Anything that doesn't is flagged for the human reviewer (and the
run report) — invented statistics were a core problem of the old channel.

Small structural counts (0-10, e.g. "three steps") are allowed.
"""

import re
from typing import Dict, Iterable, List, Set

NUM_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")


def _norm(tok: str) -> str:
    t = tok.replace(",", "").replace("$", "").rstrip("%")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def numbers_in(text: str) -> Set[str]:
    return {_norm(m.group()) for m in NUM_RE.finditer(text or "")}


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


def unsupported_numbers(script: Dict, source_text: str) -> List[Dict]:
    """Return [{shot, number, where}] for numbers not found in the source."""
    allowed = numbers_in(source_text)
    flags = []
    for i, shot in enumerate(script.get("shots", [])):
        found = [(n, "narration") for n in numbers_in(shot.get("text", ""))]
        found += [(n, "scene") for n in _scene_numbers(shot.get("scene", {}))]
        for n, where in found:
            try:
                small = float(n) <= 10
            except ValueError:
                small = False
            if not small and n not in allowed:
                flags.append({"shot": i, "number": n, "where": where})
    return flags
