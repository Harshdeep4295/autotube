"""
Scene catalogue + validator for the animated explainer (single source of truth).

The LLM writes one narration line per shot and picks a scene from CATALOGUE for it.
`validate_and_repair()` makes any LLM output safe to render: it trims text to the
limits each scene is designed for (so nothing overflows the frame), coerces
numbers, clamps list sizes, and replaces broken or unknown scenes with a
`key_point` card. It never raises on bad scene data — it records repairs instead.

The Remotion side (video/explainer/src/scenes/*) implements one component per
entry. Keep both in sync; `python -m agents.scene_schema --fixtures` exports test
fixtures the Remotion scene tests render.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

ICONS = [
    "ai", "alert", "battery", "book", "brain", "chart", "chat", "check", "clock", "cloud",
    "code", "cpu", "database", "dollar", "download", "file", "gear", "globe", "gpu", "image",
    "key", "laptop", "lightbulb", "lock", "memory", "mic", "offline", "phone", "rocket",
    "search", "server", "shield", "star", "terminal", "trending-down", "trending-up",
    "upload", "user", "users", "video", "x", "zap",
]


# ── prop specs ────────────────────────────────────────────────────────────────

@dataclass
class P:
    """A prop spec. kind: text | number | bool | enum | icon | list | obj"""
    kind: str
    max_len: int = 0                  # text
    required: bool = False
    options: Tuple[str, ...] = ()     # enum
    item: Optional["P"] = None        # list
    fields: Dict[str, "P"] = field(default_factory=dict)  # obj
    min_items: int = 0
    max_items: int = 0
    default: Any = None


def T(n: int, required: bool = False, default: Any = "") -> P:
    return P("text", max_len=n, required=required, default=default)


def N(required: bool = False, default: Any = None) -> P:
    return P("number", required=required, default=default)


def E(*opts: str, default: Optional[str] = None) -> P:
    return P("enum", options=opts, default=default if default is not None else opts[0])


def I(default: str = "lightbulb") -> P:
    return P("icon", default=default)


def L(item: P, lo: int, hi: int) -> P:
    return P("list", item=item, min_items=lo, max_items=hi, required=True)


def O(**fields: P) -> P:
    return P("obj", fields=fields)


CATALOGUE: Dict[str, Dict[str, Any]] = {
    "title_hook": {
        "use": "opening shot: the video's promise in a few words",
        "props": {"headline": T(40, True), "subline": T(70), "icon": I("rocket")},
        "example": {"headline": "RUN AI OFFLINE", "subline": "on the laptop you already own", "icon": "laptop"},
    },
    "key_point": {
        "use": "one idea in a few words (also the fallback for anything else)",
        "props": {"text": T(48, True), "sub": T(70), "icon": I()},
        "example": {"text": "Your data stays on your disk", "sub": "nothing is uploaded", "icon": "lock"},
    },
    "big_number": {
        "use": "one striking figure that is stated in the narration",
        "props": {"value": N(True), "prefix": T(3), "unit": T(8), "label": T(48, True),
                  "decimals": E("0", "1", "2")},
        "example": {"value": 5, "prefix": "", "unit": "GB", "label": "memory for an 8B model at 4-bit", "decimals": "0"},
    },
    "compare": {
        "use": "A versus B on one metric",
        "props": {"metric": T(28, True),
                  "left": O(label=T(18, True), value=T(14, True)),
                  "right": O(label=T(18, True), value=T(14, True)),
                  "winner": E("none", "left", "right")},
        "example": {"metric": "Monthly cost", "left": {"label": "Cloud AI", "value": "$20"},
                    "right": {"label": "Local AI", "value": "$0"}, "winner": "right"},
    },
    "bar_chart": {
        "use": "2-6 values compared (sizes, speeds, prices)",
        "props": {"title": T(40, True), "unit": T(8),
                  "items": L(O(label=T(14, True), value=N(True)), 2, 6)},
        "example": {"title": "Model size vs memory", "unit": "GB",
                    "items": [{"label": "3B", "value": 2}, {"label": "8B", "value": 5}, {"label": "70B", "value": 40}]},
    },
    "line_trend": {
        "use": "a value changing over time (3-8 points)",
        "props": {"title": T(40, True), "unit": T(8),
                  "points": L(O(x=T(8, True), y=N(True)), 3, 8)},
        "example": {"title": "Open models keep getting smaller", "unit": "B",
                    "points": [{"x": "2023", "y": 70}, {"x": "2024", "y": 34}, {"x": "2025", "y": 14}, {"x": "2026", "y": 8}]},
    },
    "steps": {
        "use": "an ordered how-to (2-5 steps)",
        "props": {"title": T(40, True), "items": L(T(40, True), 2, 5)},
        "example": {"title": "Get started in 3 steps",
                    "items": ["Install Ollama", "Pull a small model", "Start chatting"]},
    },
    "checklist": {
        "use": "requirements or pros/cons (2-5 rows)",
        "props": {"title": T(40, True), "items": L(O(text=T(40, True), ok=P("bool", default=True)), 2, 5)},
        "example": {"title": "What you need", "items": [{"text": "16 GB of RAM", "ok": True},
                                                        {"text": "A graphics card", "ok": False}]},
    },
    "icon_grid": {
        "use": "several things at once (2-6 labelled icons)",
        "props": {"title": T(40, True), "items": L(O(icon=I(), label=T(18, True)), 2, 6)},
        "example": {"title": "Three things you need", "items": [{"icon": "gear", "label": "The tool"},
                                                                {"icon": "brain", "label": "A model"},
                                                                {"icon": "memory", "label": "Memory"}]},
    },
    "meter": {
        "use": "how much of a capacity something uses (fits / doesn't fit)",
        "props": {"label": T(40, True), "value": N(True), "max": N(True), "unit": T(8), "note": T(40)},
        "example": {"label": "8B model in 16 GB of RAM", "value": 5, "max": 16, "unit": "GB", "note": "fits comfortably"},
    },
    "terminal": {
        "use": "commands or code; lines starting with '$ ' are typed",
        "props": {"title": T(24, default="Terminal"), "lines": L(T(48, True), 1, 5)},
        "example": {"title": "Terminal", "lines": ["$ ollama run llama3.1", "pulling model... done", ">>> Send a message"]},
    },
    "chat": {
        "use": "an example conversation with an AI assistant (1-3 messages)",
        "props": {"title": T(24, default="Chat"),
                  "messages": L(O(sender=E("user", "ai"), text=T(56, True)), 1, 3)},
        "example": {"title": "LM Studio", "messages": [{"sender": "user", "text": "Summarize my meeting notes"},
                                                       {"sender": "ai", "text": "Here are the 3 key decisions..."}]},
    },
    "timeline": {
        "use": "dated events in order (2-5)",
        "props": {"title": T(40, True), "events": L(O(date=T(10, True), label=T(28, True)), 2, 5)},
        "example": {"title": "How we got here", "events": [{"date": "2023", "label": "First open 7B models"},
                                                           {"date": "2026", "label": "Laptop-class models"}]},
    },
    "quote": {
        "use": "a short statement from the source, with attribution",
        "props": {"text": T(120, True), "attribution": T(40)},
        "example": {"text": "The best model is the one you can actually run.", "attribution": "Project docs"},
    },
    "cta_end": {
        "use": "final shot: a question for the comments",
        "props": {"question": T(60, True), "sub": T(60, default="Subscribe for more practical AI")},
        "example": {"question": "Which model will you try first?", "sub": "Subscribe for more practical AI"},
    },
}


# ── repair helpers ───────────────────────────────────────────────────────────

def _trim(s: Any, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s if s is not None else "")).strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0].rstrip(",.;:-–— ")
    return (cut or s[: n - 1]) + "…"


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v or "").replace(",", ""))
    return float(m.group()) if m else None


class _Invalid(Exception):
    pass


def _coerce(spec: P, value: Any, path: str, repairs: List[str]) -> Any:
    if spec.kind == "text":
        if value is None or str(value).strip() == "":
            if spec.required:
                raise _Invalid(f"{path}: missing text")
            return spec.default or ""
        out = _trim(value, spec.max_len)
        if out != str(value).strip():
            repairs.append(f"{path}: trimmed to {spec.max_len} chars")
        return out
    if spec.kind == "number":
        n = _num(value)
        if n is None:
            if spec.required:
                raise _Invalid(f"{path}: not a number ({value!r})")
            return spec.default
        return n
    if spec.kind == "bool":
        if isinstance(value, bool):
            return value
        if value is None:
            return bool(spec.default)
        return str(value).strip().lower() in ("true", "yes", "1", "ok", "y")
    if spec.kind == "enum":
        v = str(value if value is not None else "").strip().lower()
        if v not in spec.options:
            if value is not None:
                repairs.append(f"{path}: {value!r} → {spec.default!r}")
            return spec.default
        return v
    if spec.kind == "icon":
        v = str(value or "").strip().lower()
        if v not in ICONS:
            if value:
                repairs.append(f"{path}: unknown icon {value!r} → {spec.default!r}")
            return spec.default
        return v
    if spec.kind == "obj":
        if not isinstance(value, dict):
            raise _Invalid(f"{path}: expected object")
        return {k: _coerce(s, value.get(k), f"{path}.{k}", repairs) for k, s in spec.fields.items()}
    if spec.kind == "list":
        if not isinstance(value, list):
            raise _Invalid(f"{path}: expected list")
        items = []
        for i, it in enumerate(value):
            try:
                items.append(_coerce(spec.item, it, f"{path}[{i}]", repairs))
            except _Invalid as e:
                repairs.append(f"{e} (item dropped)")
        if len(items) > spec.max_items:
            repairs.append(f"{path}: {len(items)} items → {spec.max_items}")
            items = items[: spec.max_items]
        if len(items) < spec.min_items:
            raise _Invalid(f"{path}: needs ≥{spec.min_items} valid items, got {len(items)}")
        return items
    raise ValueError(f"unknown spec kind {spec.kind}")


def key_point_from(shot: Dict) -> Dict:
    emph = [e for e in (shot.get("emphasis") or []) if isinstance(e, str) and e.strip()]
    text = emph[0] if emph else " ".join(str(shot.get("text", "")).split()[:6])
    return {"type": "key_point", "props": {"text": _trim(text, 48), "sub": "", "icon": "lightbulb"}}


def repair_scene(scene: Any, shot: Dict, where: str, repairs: List[str]) -> Dict:
    if not isinstance(scene, dict) or scene.get("type") not in CATALOGUE:
        t = scene.get("type") if isinstance(scene, dict) else scene
        repairs.append(f"{where}: unknown scene {t!r} → key_point")
        return key_point_from(shot)
    stype = scene["type"]
    props_in = scene.get("props") if isinstance(scene.get("props"), dict) else {}
    try:
        props = {k: _coerce(s, props_in.get(k), f"{where}.{stype}.{k}", repairs)
                 for k, s in CATALOGUE[stype]["props"].items()}
    except _Invalid as e:
        repairs.append(f"{e} → key_point")
        return key_point_from(shot)
    if stype == "meter" and (props["max"] is None or props["max"] <= 0):
        repairs.append(f"{where}: meter max ≤ 0 → key_point")
        return key_point_from(shot)
    if stype == "meter":
        props["value"] = max(0.0, min(props["value"], props["max"]))
    return {"type": stype, "props": props}


def validate_and_repair(script: Dict) -> Tuple[Dict, List[str]]:
    """Return (safe_script, repairs). Raises ValueError only if there is no usable narration."""
    repairs: List[str] = []
    shots_in = script.get("shots")
    if not isinstance(shots_in, list):
        raise ValueError("script has no 'shots' list")
    shots = []
    for i, s in enumerate(shots_in):
        if not isinstance(s, dict) or not str(s.get("text", "")).strip():
            repairs.append(f"shot {i}: no narration text → dropped")
            continue
        text = re.sub(r"\s+", " ", str(s["text"])).strip()
        emph = [e.strip() for e in (s.get("emphasis") or []) if isinstance(e, str) and e.strip()]
        kept = [e for e in emph if e.lower() in text.lower()]
        if len(kept) != len(emph):
            repairs.append(f"shot {i}: emphasis not found in text dropped")
        shot = {"text": text, "emphasis": kept[:3]}
        if isinstance(s.get("chapter"), str) and s["chapter"].strip():
            shot["chapter"] = _trim(s["chapter"], 40)
        shot["scene"] = repair_scene(s.get("scene"), shot, f"shot {i}", repairs)
        shots.append(shot)
    if not shots:
        raise ValueError("script has no usable shots")
    if shots[-1]["scene"]["type"] != "cta_end":
        repairs.append("last shot is not cta_end (kept as is)")
    out = dict(script)
    out["shots"] = shots
    return out, repairs


# ── prompt + fixtures ────────────────────────────────────────────────────────

def _describe(spec: P) -> str:
    if spec.kind == "text":
        return f"text≤{spec.max_len}" + ("" if spec.required else "?")
    if spec.kind == "number":
        return "number" + ("" if spec.required else "?")
    if spec.kind == "bool":
        return "bool"
    if spec.kind == "enum":
        return "|".join(spec.options)
    if spec.kind == "icon":
        return "icon"
    if spec.kind == "obj":
        return "{" + ", ".join(f"{k}: {_describe(v)}" for k, v in spec.fields.items()) + "}"
    if spec.kind == "list":
        return f"[{spec.min_items}-{spec.max_items} × {_describe(spec.item)}]"
    return spec.kind


def catalogue_for_prompt() -> str:
    lines = []
    for name, c in CATALOGUE.items():
        props = ", ".join(f"{k}: {_describe(v)}" for k, v in c["props"].items())
        lines.append(f"- {name} — {c['use']}. props: {props}")
    lines.append("icons: " + ", ".join(ICONS))
    return "\n".join(lines)


def _max_value(spec: P, seed: str) -> Any:
    if spec.kind == "text":
        base = (seed.upper() + " WWWW MMMM " * 20)
        return base[: spec.max_len]
    if spec.kind == "number":
        return 88888.88
    if spec.kind == "bool":
        return False
    if spec.kind == "enum":
        return spec.options[-1]
    if spec.kind == "icon":
        return "trending-down"
    if spec.kind == "obj":
        return {k: _max_value(v, k) for k, v in spec.fields.items()}
    if spec.kind == "list":
        return [_max_value(spec.item, f"{seed}{i}") for i in range(spec.max_items)]


def fixtures() -> List[Dict]:
    """Two fixtures per scene: the catalogue example and one at every limit."""
    out = []
    for name, c in CATALOGUE.items():
        out.append({"id": f"{name}--example", "type": name, "props": c["example"]})
        props = {k: _max_value(v, k) for k, v in c["props"].items()}
        if name == "meter":
            props["max"] = 99999.99
        shot = {"text": "fixture", "emphasis": []}
        repaired = repair_scene({"type": name, "props": props}, shot, name, [])
        assert repaired["type"] == name, f"max fixture for {name} failed validation"
        out.append({"id": f"{name}--max", "type": name, "props": repaired["props"]})
    return out


if __name__ == "__main__":
    if "--fixtures" in sys.argv:
        print(json.dumps(fixtures(), indent=1, ensure_ascii=False))
    else:
        print(catalogue_for_prompt())
