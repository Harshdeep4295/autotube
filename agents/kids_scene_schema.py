"""
Story-scene catalogue + validator for the kids explainer ("Explained Like You're 5").

A kids script is a list of SCENES. Each scene has a type from CATALOGUE, props, a
weather, and 1-6 narration LINES. Line i triggers beat i of the scene (see "beats"),
optionally on a cue word inside that line, so the picture changes exactly when the
narrator says it.

`validate_and_repair()` makes any LLM output safe to render (same contract as
agents/scene_schema.py): trims text, clamps numbers and lists, maps unknown
props/characters to safe defaults, and turns broken scenes into a `talk` scene.
It never raises on bad scene data — only when there is no narration at all.

The renderer lives in agents/kids/scenes.py (one function per catalogue entry);
tests/test_kids_scene_schema.py keeps both in sync.
"""

import json
import re
import sys
from typing import Any, Dict, List, Tuple

from agents.scene_schema import E, L, N, O, P, T, _coerce, _Invalid, _trim

PROPS = (
    "coin", "lemon", "cup", "jar", "pizza", "slice", "apple", "cookie", "toy", "book", "bulb", "heart",
    "star", "letter", "phone", "laptop", "robot", "cloud", "server", "lock", "key", "gift", "seed",
    "tree", "battery", "stand", "shop", "bank", "house", "truck", "rocket", "piggy", "box", "chip",
    "water", "chart", "switch", "door", "mailbox", "puzzle", "gear",
)
CHARACTERS = ("mia", "leo", "zoe", "sam", "ava", "raj", "kim")
WEATHER = ("sunny", "rainy", "night")
MAX_LINE_WORDS = 18


def PR(default: str = "star") -> P:
    return E(*PROPS, default=default)


def WHO(default: str = "mia") -> P:
    return E(*CHARACTERS, default=default)


CATALOGUE: Dict[str, Dict[str, Any]] = {
    "title": {
        "use": "first scene: the big question of the video",
        "lines": (1, 3),
        "beats": ["title card pops up", "the props bounce in", "Mia waves hello"],
        "props": {"question": T(44, True), "props": L(PR(), 0, 3)},
        "example": {"question": "How does the stock market work?", "props": ["coin", "lemon"]},
    },
    "meet": {
        "use": "introduce a character and their place/thing (the analogy's 'company')",
        "lines": (1, 3),
        "beats": ["character walks in and says hi", "their place pops up", "customers bring items into the jar"],
        "props": {"who": WHO(), "place": PR("stand"), "label": T(12), "greeting": T(22), "flow": PR("coin")},
        "example": {"who": "mia", "place": "stand", "label": "LEMONADE", "greeting": "Hi! I'm Mia!", "flow": "coin"},
    },
    "wants": {
        "use": "a character dreams of something but cannot afford it (a problem to solve)",
        "lines": (1, 3),
        "beats": ["thought bubble shows the dream", "a 'need' tag shows the cost", "a 'have' tag shows what they have; they look sad"],
        "props": {"who": WHO(), "dream": PR("stand"), "dream_label": T(12), "need": N(default=100), "have": N(default=5),
                  "unit": PR("coin")},
        "example": {"who": "mia", "dream": "stand", "dream_label": "BIG STAND", "need": 100, "have": 5, "unit": "coin"},
    },
    "split": {
        "use": "split one whole thing into equal pieces (shares, slices, parts)",
        "lines": (1, 4),
        "beats": ["an idea bulb appears", "the thing turns into a round pie with a label", "it gets cut into pieces",
                  "one piece slides out with a name badge"],
        "props": {"who": WHO(), "whole": PR("stand"), "whole_label": T(20), "pieces": N(default=8),
                  "piece_name": T(14, True)},
        "example": {"who": "mia", "whole": "stand", "whole_label": "Mia's Lemonade", "pieces": 10, "piece_name": "1 SHARE"},
    },
    "trade": {
        "use": "one character gives something to each buyer and gets something back (buying/selling/paying)",
        "lines": (2, 5),
        "beats": ["the seller stands ready", "buyer 1 trades", "buyer 2 trades", "buyer 3 trades", "buyer 4 trades"],
        "props": {"seller": WHO(), "buyers": L(WHO("leo"), 1, 4), "gives": PR("slice"), "gets": PR("coin"),
                  "each": N(default=1)},
        "example": {"seller": "mia", "buyers": ["leo", "zoe"], "gives": "slice", "gets": "coin", "each": 10},
    },
    "grow": {
        "use": "something small becomes big (growth, interest, a business growing)",
        "lines": (1, 3),
        "beats": ["the small thing appears with its label", "it grows big with sparkles", "the character cheers"],
        "props": {"who": WHO(), "small": PR("stand"), "big": PR("stand"), "label_before": T(14), "label_after": T(14)},
        "example": {"who": "mia", "small": "stand", "big": "stand", "label_before": "small", "label_after": "BIG!"},
    },
    "crowd": {
        "use": "many kids want the same thing (demand, popularity)",
        "lines": (1, 3),
        "beats": ["the wanted thing appears big", "kids shout that they want it", "hearts float up"],
        "props": {"thing": PR("slice"), "label": T(16), "shouts": L(T(10, True), 1, 4)},
        "example": {"thing": "slice", "label": "Mia's slice", "shouts": ["Me!", "Me too!", "Please!"]},
    },
    "chart": {
        "use": "a value going up, down, or bouncing up and down over time",
        "lines": (1, 3),
        "beats": ["the line starts drawing", "the title badge appears", "the line finishes"],
        "props": {"mode": E("up", "down", "bouncy"), "title": T(22), "who": WHO()},
        "example": {"mode": "up", "title": "PRICE GOES UP!", "who": "leo"},
    },
    "price": {
        "use": "the price of one thing changes from an old number to a new number",
        "lines": (1, 3),
        "beats": ["the character holds the item with the old price tag", "the tag flips to the new price", "an arrow shows up or down"],
        "props": {"who": WHO("leo"), "item": PR("slice"), "old": N(default=1), "new": N(default=3), "unit": PR("coin")},
        "example": {"who": "leo", "item": "slice", "old": 1, "new": 3, "unit": "coin"},
    },
    "many": {
        "use": "lots of places/things at once (a market, a network, many companies)",
        "lines": (1, 4),
        "beats": ["the ground/fence appears", "the places pop in one by one", "little kids walk between them carrying things",
                  "the reveal banner drops in with confetti"],
        "props": {"items": L(O(prop=PR("shop"), label=T(10, True)), 2, 6), "reveal": T(18), "carry": PR("coin")},
        "example": {"items": [{"prop": "shop", "label": "TOYS"}, {"prop": "stand", "label": "LEMONADE"},
                              {"prop": "phone", "label": "PHONES"}], "reveal": "STOCK MARKET", "carry": "slice"},
    },
    "steps": {
        "use": "something travels step by step (how a message, money or a package moves)",
        "lines": (2, 5),
        "beats": ["step 1 appears", "step 2 appears and a traveller moves there", "step 3", "step 4", "step 5"],
        "props": {"items": L(O(prop=PR("phone"), label=T(12, True)), 2, 5), "traveller": PR("letter")},
        "example": {"items": [{"prop": "phone", "label": "Your phone"}, {"prop": "cloud", "label": "The internet"},
                              {"prop": "phone", "label": "Grandma"}], "traveller": "letter"},
    },
    "compare": {
        "use": "two things side by side (this vs that)",
        "lines": (1, 3),
        "beats": ["the left thing appears", "the right thing appears", "the winner gets a star"],
        "props": {"left": O(prop=PR("piggy"), label=T(14, True)), "right": O(prop=PR("bank"), label=T(14, True)),
                  "winner": E("none", "left", "right")},
        "example": {"left": {"prop": "piggy", "label": "Piggy bank"}, "right": {"prop": "bank", "label": "Real bank"},
                    "winner": "right"},
    },
    "reveal": {
        "use": "say the grown-up word out loud, big (the name of the concept)",
        "lines": (1, 2),
        "beats": ["big banner with the word and confetti", "the small explanation appears"],
        "props": {"word": T(18, True), "sub": T(36), "prop": PR("star")},
        "example": {"word": "STOCK MARKET", "sub": "where people buy and sell shares", "prop": "chart"},
    },
    "talk": {
        "use": "a character says one simple idea (fallback for anything else)",
        "lines": (1, 3),
        "beats": ["the character and the thing appear", "the speech bubble appears", "the thing bounces"],
        "props": {"who": WHO(), "bubble": T(60, True), "prop": PR("star")},
        "example": {"who": "zoe", "bubble": "Be patient!", "prop": "tree"},
    },
    "recap": {
        "use": "remember the grown-up words: each card = grown-up word + kid meaning",
        "lines": (2, 4),
        "beats": ["the 'Let's remember!' header", "card 1", "card 2", "card 3"],
        "props": {"cards": L(O(prop=PR(), term=T(14, True), means=T(30, True)), 1, 3)},
        "example": {"cards": [{"prop": "stand", "term": "COMPANY", "means": "a lemonade stand"},
                              {"prop": "slice", "term": "SHARE", "means": "one slice"}]},
    },
    "outro": {
        "use": "last scene: the cast waves goodbye",
        "lines": (1, 2),
        "beats": ["the cast waves", "the goodbye message and confetti"],
        "props": {"cast": L(WHO(), 1, 3), "message": T(34, default="Great job, friend!")},
        "example": {"cast": ["leo", "mia", "zoe"], "message": "Great job, friend!"},
    },
}


def talk_from(lines: List[Dict]) -> Dict:
    first = lines[0]["text"] if lines else "Let's learn!"
    return {"type": "talk", "weather": "sunny",
            "props": {"who": "mia", "bubble": _trim(" ".join(first.split()[:7]), 40), "prop": "star"}}


def _clean_lines(raw: Any, where: str, repairs: List[str]) -> List[Dict]:
    out = []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return out
    for i, ln in enumerate(raw):
        if isinstance(ln, str):
            ln = {"text": ln}
        if not isinstance(ln, dict) or not str(ln.get("text", "")).strip():
            repairs.append(f"{where}.line {i}: empty → dropped")
            continue
        text = re.sub(r"\s+", " ", str(ln["text"])).strip()
        item = {"text": text}
        cue = str(ln.get("cue") or "").strip()
        if cue:
            if cue.lower() in text.lower():
                item["cue"] = cue
            else:
                repairs.append(f"{where}.line {i}: cue {cue!r} not in text → dropped")
        out.append(item)
    return out


def repair_scene(scene: Any, where: str, repairs: List[str]) -> Dict:
    if not isinstance(scene, dict):
        repairs.append(f"{where}: not an object → dropped")
        return {}
    lines = _clean_lines(scene.get("lines"), where, repairs)
    if not lines:
        repairs.append(f"{where}: no narration → dropped")
        return {}
    stype = scene.get("type")
    weather = str(scene.get("weather") or "sunny").lower()
    if weather not in WEATHER:
        repairs.append(f"{where}: weather {weather!r} → sunny")
        weather = "sunny"
    if stype not in CATALOGUE:
        repairs.append(f"{where}: unknown scene {stype!r} → talk")
        out = talk_from(lines)
        out["lines"] = lines
        return out
    spec = CATALOGUE[stype]
    props_in = dict(scene.get("props")) if isinstance(scene.get("props"), dict) else {}
    for k, s in spec["props"].items():  # optional lists may be omitted
        if s.kind == "list" and s.min_items == 0 and not isinstance(props_in.get(k), list):
            props_in[k] = []
    try:
        props = {k: _coerce(s, props_in.get(k), f"{where}.{stype}.{k}", repairs) for k, s in spec["props"].items()}
    except _Invalid as e:
        repairs.append(f"{e} → talk")
        out = talk_from(lines)
        out["lines"] = lines
        return out
    # numeric sanity
    for k in ("need", "have", "old", "new", "each"):
        if k in props and props[k] is not None:
            props[k] = max(0.0, min(float(props[k]), 9999.0))
    if stype == "split":
        props["pieces"] = int(max(2, min(12, props.get("pieces") or 8)))
    lo, hi = spec["lines"]
    if stype == "trade":
        hi = min(hi, 1 + len(props["buyers"]))
    if len(lines) > hi:
        # keep every word: merge the overflow into the last allowed line
        head, tail = lines[:hi - 1], lines[hi - 1:]
        merged = {"text": " ".join(l["text"] for l in tail)}
        if tail[0].get("cue"):
            merged["cue"] = tail[0]["cue"]
        lines = head + [merged]
        repairs.append(f"{where}: {stype} takes ≤{hi} lines → merged the rest")
    return {"type": stype, "weather": weather, "props": props, "lines": lines}


def _no_ellipsis(v: Any) -> Any:
    if isinstance(v, str):
        return v[:-1].rstrip() if v.endswith("…") and len(v) <= 24 else v
    if isinstance(v, list):
        return [_no_ellipsis(x) for x in v]
    if isinstance(v, dict):
        return {k: _no_ellipsis(x) for k, x in v.items()}
    return v


def validate_and_repair(script: Dict) -> Tuple[Dict, List[str]]:
    """Return (safe_script, repairs). Raises ValueError only if nothing is narratable."""
    repairs: List[str] = []
    scenes_in = script.get("scenes")
    if not isinstance(scenes_in, list):
        raise ValueError("kids script has no 'scenes' list")
    scenes = [s for s in (repair_scene(sc, f"scene {i}", repairs) for i, sc in enumerate(scenes_in)) if s]
    if not scenes:
        raise ValueError("kids script has no usable scenes")
    if scenes[0]["type"] != "title":
        repairs.append("first scene is not 'title' (kept as is)")
    if scenes[-1]["type"] != "outro":
        repairs.append("added an 'outro' scene")
        scenes.append({"type": "outro", "weather": "sunny", "props": {"cast": ["leo", "mia", "zoe"],
                       "message": "Great job, friend!"}, "lines": [{"text": "Great job today, friend! See you next time!"}]})
    for sc in scenes:
        for ln in sc["lines"]:
            if len(ln["text"].split()) > MAX_LINE_WORDS:
                repairs.append(f"long line ({len(ln['text'].split())} words): {ln['text'][:40]}…")
    for sc in scenes:   # a short label cut at a word reads fine without the "…" ("GRANDMA'S", not "GRANDMA'S…")
        sc["props"] = _no_ellipsis(sc["props"])
    out = dict(script)
    out["scenes"] = scenes
    return out, repairs


def word_count(script: Dict) -> int:
    return sum(len(ln["text"].split()) for sc in script.get("scenes", []) for ln in sc.get("lines", []))


def _describe(spec: P) -> str:
    if spec.kind == "text":
        return f"text≤{spec.max_len}" + ("" if spec.required else "?")
    if spec.kind == "number":
        return "number"
    if spec.kind == "bool":
        return "bool"
    if spec.kind == "enum":
        if spec.options == PROPS:
            return "prop"
        if spec.options == CHARACTERS:
            return "character"
        return "|".join(spec.options)
    if spec.kind == "obj":
        return "{" + ", ".join(f"{k}: {_describe(v)}" for k, v in spec.fields.items()) + "}"
    if spec.kind == "list":
        return f"[{spec.min_items}-{spec.max_items} × {_describe(spec.item)}]"
    return spec.kind


def catalogue_for_prompt() -> str:
    out = []
    for name, c in CATALOGUE.items():
        lo, hi = c["lines"]
        props = ", ".join(f"{k}: {_describe(v)}" for k, v in c["props"].items())
        beats = "; ".join(f"line {i + 1} → {b}" for i, b in enumerate(c["beats"][:hi]))
        out.append(f"- {name} ({lo}-{hi} lines) — {c['use']}. props: {props}. beats: {beats}. "
                   f"example props: {json.dumps(c['example'])}")
    out.append("props (things you can show): " + ", ".join(PROPS))
    out.append("characters: mia, leo, zoe (main cast); sam, ava, raj, kim (friends)")
    return "\n".join(out)


if __name__ == "__main__":
    print(catalogue_for_prompt() if "--fixtures" not in sys.argv else json.dumps(CATALOGUE, default=str)[:2000])
