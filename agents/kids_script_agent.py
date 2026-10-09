"""
Kids script agent: topic → analogy plan → scenes script → checker (+1 fix round) → length guard.

Short videos (≈300 words), so each step is one small free-tier call. Scene problems are
fixed by agents.kids_scene_schema.validate_and_repair, never fatal.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from agents.explainer_script_agent import parse_json_obj
from agents.kids_scene_schema import PROPS, catalogue_for_prompt, validate_and_repair, word_count
from agents.llm import FreeLLM
from config import config
from templates import kids_prompts as P

REPO = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


def _need_ok(o: Dict) -> None:
    if not isinstance(o.get("ok"), bool):
        raise ValueError("missing boolean 'ok'")


def estimated_seconds(words: int) -> float:
    return words / max(60, config.KIDS_WPM) * 60


def word_bounds():
    target = config.KIDS_TARGET_WORDS
    # keep the estimate inside [MIN, MAX] seconds
    lo = max(round(target * 0.8), round(config.KIDS_MIN_SECONDS / 60 * config.KIDS_WPM))
    hi = min(round(target * 1.2), round((config.KIDS_MAX_SECONDS - 15) / 60 * config.KIDS_WPM))
    return lo, max(lo + 20, hi)


# Story worlds the prop kit can draw. One is picked per video, least recently used first, so
# two videos in a row never share a setting. "areas" = where the world fits best.
WORLDS = (
    {"key": "toy shop", "backdrop": "town", "world": "Leo's toy shop", "place": "shop", "label": "TOYS", "items": "toy, coin, box, gift", "areas": ("finance",)},
    {"key": "robot workshop", "backdrop": "workshop", "world": "Zoe's robot workshop", "place": "robot", "label": "ROBOTS", "items": "robot, chip, battery, bulb", "areas": ("tech",)},
    {"key": "cookie bakery", "backdrop": "kitchen", "world": "Mia's cookie bakery", "place": "jar", "label": "COOKIES", "items": "cookie, coin, jar, box", "areas": ("finance",)},
    {"key": "letters to grandma", "backdrop": "town", "world": "sending letters to Grandma's house", "place": "house", "label": "GRANDMA", "items": "letter, truck, key, lock", "areas": ("tech",)},
    {"key": "apple tree", "backdrop": "garden", "world": "the apple tree in Zoe's garden", "place": "tree", "label": "APPLES", "items": "apple, seed, water, jar", "areas": ("finance", "tech")},
    {"key": "delivery truck", "backdrop": "town", "world": "Leo's delivery truck", "place": "truck", "label": "DELIVERY", "items": "box, gift, letter, key", "areas": ("tech", "finance")},
    {"key": "pizza shop", "backdrop": "kitchen", "world": "Mia's pizza shop", "place": "pizza", "label": "PIZZA", "items": "pizza, slice, coin", "areas": ("finance",)},
    {"key": "rocket club", "backdrop": "space", "world": "the kids' rocket club", "place": "rocket", "label": "ROCKET", "items": "star, battery, chip, bulb", "areas": ("tech",)},
    {"key": "piggy bank", "backdrop": "room", "world": "the piggy bank in Leo's house", "place": "piggy", "label": "PIGGY BANK", "items": "piggy, coin, jar, gift", "areas": ("finance",)},
    {"key": "book swap", "backdrop": "room", "world": "the book swap at Zoe's house", "place": "book", "label": "BOOKS", "items": "book, box, star, key", "areas": ("tech", "finance")},
    {"key": "lemonade stand", "backdrop": "meadow", "world": "Mia's lemonade stand", "place": "stand", "label": "LEMONADE", "items": "lemon, cup, coin, jar", "areas": ("finance",)},
)


def pick_world(area: str = "", history: Optional[List[Dict]] = None) -> Dict:
    """The world used longest ago (never-used first), preferring ones that fit the topic's area.
    History rows from before worlds were recorded count as the lemonade stand."""
    if history is None:
        try:
            history = json.loads((REPO / config.KIDS_HISTORY_FILE).read_text())
        except Exception:  # noqa: BLE001
            history = []
    used = [h.get("world") or "lemonade stand" for h in history]
    last = {w["key"]: max((i for i, u in enumerate(used) if u == w["key"]), default=-1) for w in WORLDS}
    fits = [w for w in WORLDS if area in w["areas"]] or list(WORLDS)
    return min(fits, key=lambda w: last[w["key"]])


def swap_stand(script: Dict, place: str) -> int:
    """Models keep reaching for the lemonade stall ("stand") whatever the world is. In a world
    with another main place, redraw every stand as that place. Returns how many were changed."""
    if place == "stand":
        return 0
    n = 0

    def fix(v):
        nonlocal n
        if v == "stand":
            n += 1
            return place
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        return v

    for sc in script.get("scenes", []):
        if isinstance(sc, dict) and isinstance(sc.get("props"), dict):
            sc["props"] = {k: (v if k in ("label", "greeting", "question") else fix(v)) for k, v in sc["props"].items()}
    return n


SHORT_WORDS = (60, 95)       # ≈ 30-40 s at the kids narration pace
SHORT_MAX_WORDS = 110
SHORT_OUTRO = "Want the whole story? Watch the full video!"


def _words(scenes: List[Dict]) -> int:
    return sum(len(str(ln.get("text", "")).split()) for sc in scenes for ln in sc.get("lines", []))


def finish_short(scenes: List[Dict]) -> List[Dict]:
    """Shape scenes into a Short: no title card, at most SHORT_MAX_WORDS, and a fixed closing
    line that points to the full video."""
    body = [sc for sc in scenes if isinstance(sc, dict) and sc.get("type") not in ("title", "outro") and sc.get("lines")]
    while len(body) > 2 and _words(body) > SHORT_MAX_WORDS - len(SHORT_OUTRO.split()):
        body.pop()
    return body + [{"type": "outro", "weather": "sunny",
                    "props": {"cast": ["leo", "mia", "zoe"], "message": "Full video on the channel!"},
                    "lines": [{"text": SHORT_OUTRO}]}]


def short_cut(script: Dict) -> List[Dict]:
    """A Short without an LLM: the start of the story (after the title card), up to about 75 words."""
    body, n = [], 0
    for sc in script.get("scenes", [])[1:]:
        if sc.get("type") in ("title", "outro", "recap"):
            continue
        w = _words([sc])
        if body and n + w > 75:
            break
        body.append(sc)
        n += w
    return finish_short(body)


class KidsScriptAgent:
    def __init__(self, llm: Optional[FreeLLM] = None):
        self.llm = llm or FreeLLM()

    def _ask(self, user: str, check, max_tokens: int = 6000, repairs: int = 2) -> Dict:
        prompt = user
        for attempt in range(repairs + 1):
            text = self.llm.complete(P.SYSTEM, prompt, max_tokens=max_tokens, temperature=0.7)
            try:
                obj = parse_json_obj(text)
                check(obj)
                return obj
            except ValueError as e:
                if attempt == repairs:
                    raise
                logger.warning(f"[kids-script] unusable response ({e}) — asking for a repair")
                prompt = user + "\n\n" + P.REPAIR_USER.format(error=str(e)[:300])
        raise ValueError("unreachable")

    def plan(self, topic: Dict) -> Dict:
        def check(o):
            if not str(o.get("question", "")).strip():
                raise ValueError("missing question")
            if not isinstance(o.get("map"), list) or not o["map"]:
                raise ValueError("missing map")
            if not isinstance(o.get("story"), list) or len(o["story"]) < 4:
                raise ValueError("story needs 4+ beats")

        ctx = "\n".join(x for x in (topic.get("from_headline", ""), topic.get("summary", ""), topic.get("hint", "")) if x)
        w = pick_world(topic.get("area", ""))
        self.world = w
        topic["world"] = w["key"]   # recorded in the history by mark_used after a successful upload
        logger.info(f"[kids-script] story world: {w['world']}")
        return self._ask(P.PLAN_USER.format(question=topic["topic"], context=ctx or "(none)", props=", ".join(PROPS),
                                            world=w["world"], place=w["place"], label=w["label"], items=w["items"]),
                         check, max_tokens=3000)

    def write(self, plan: Dict) -> Dict:
        lo, hi = word_bounds()

        def check(o):
            if not isinstance(o.get("scenes"), list) or len(o["scenes"]) < 5:
                raise ValueError("need 5+ scenes")
            validate_and_repair(o)

        return self._ask(P.SCRIPT_USER.format(plan=json.dumps(plan, ensure_ascii=False), min_words=lo, max_words=hi,
                                              catalogue=catalogue_for_prompt()), check, max_tokens=12000)

    def review(self, script: Dict) -> Dict:
        lo, hi = word_bounds()
        slim = {k: script[k] for k in ("title", "scenes") if k in script}
        try:
            verdict = self._ask(P.CHECK_USER.format(script=json.dumps(slim, ensure_ascii=False)),
                                _need_ok,
                                max_tokens=2000, repairs=1)
        except Exception as e:  # noqa: BLE001 — the checker is advisory
            logger.warning(f"[kids-script] checker unavailable: {str(e)[:120]}")
            return {"script": script, "review": {"ok": None, "problems": []}}
        problems = [str(p) for p in verdict.get("problems", [])][:8]
        if verdict.get("ok") or not problems:
            return {"script": script, "review": {"ok": True, "problems": problems}}
        logger.info(f"[kids-script] checker found {len(problems)} problem(s) — one fix round")
        try:
            fixed = self._ask(P.FIX_USER.format(problems="\n".join(f"- {p}" for p in problems), min_words=lo,
                                                max_words=hi, script=json.dumps(script, ensure_ascii=False)),
                              lambda o: validate_and_repair(o), max_tokens=12000, repairs=1)
            for k in ("title", "description", "tags", "thumbnail_text"):
                fixed.setdefault(k, script.get(k))
            return {"script": fixed, "review": {"ok": False, "problems": problems, "fixed": True}}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[kids-script] fix round failed ({str(e)[:120]}) — keeping original")
            return {"script": script, "review": {"ok": False, "problems": problems, "fixed": False}}

    def fit_length(self, script: Dict) -> Dict:
        lo, hi = word_bounds()
        for _ in range(2):
            safe, _ = validate_and_repair(script)
            w = word_count(safe)
            if lo <= w <= hi:
                return script
            direction = ("Add 1-3 scenes that deepen the story (not new topics)." if w < lo
                         else "Cut or merge scenes; keep the title, recap and outro.")
            logger.info(f"[kids-script] {w} words (need {lo}-{hi}) — asking to {'lengthen' if w < lo else 'shorten'}")
            try:
                script = self._ask(P.LENGTH_USER.format(words=w, min_words=lo, max_words=hi, direction=direction,
                                                        script=json.dumps(script, ensure_ascii=False)),
                                   lambda o: validate_and_repair(o), max_tokens=12000, repairs=1)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[kids-script] length fix failed: {str(e)[:120]}")
                break
        return script

    def short(self, script: Dict) -> List[Dict]:
        """Scenes of the 30-40 s Short: hook line first, one idea, pointer to the full video."""
        def check(o):
            if not isinstance(o.get("scenes"), list) or len(o["scenes"]) < 3:
                raise ValueError("need 3+ scenes")
            w = _words([sc for sc in o["scenes"] if isinstance(sc, dict)])
            if w < 40:
                raise ValueError(f"only {w} words, need {SHORT_WORDS[0]}-{SHORT_WORDS[1]}")

        full = {"title": script.get("title", ""), "scenes": script.get("scenes", [])}
        o = self._ask(P.SHORT_USER.format(script=json.dumps(full, ensure_ascii=False), min_words=SHORT_WORDS[0],
                                          max_words=SHORT_WORDS[1], catalogue=catalogue_for_prompt()),
                      check, max_tokens=6000, repairs=1)
        return finish_short(o["scenes"])

    def generate(self, topic: Dict) -> Dict:
        logger.info(f"[kids-script] topic: {topic['topic'][:70]}")
        plan = self.plan(topic)
        logger.info(f"[kids-script] analogy: {plan.get('world', '')!r} — {len(plan.get('map', []))} grown-up words")
        script = self.write(plan)
        script = self.fit_length(script)
        reviewed = self.review(script)
        script = reviewed["script"]
        script, repairs = validate_and_repair(script)
        # After the repair, not before: an unknown place ("workshop") is repaired to the default stall.
        swapped = swap_stand(script, getattr(self, "world", {}).get("place", "stand"))
        if swapped:
            logger.info(f"[kids-script] redrew {swapped} lemonade stall(s) as '{self.world['place']}'")
        words = word_count(script)
        est = estimated_seconds(words)
        if est > config.KIDS_MAX_SECONDS - 5:
            raise RuntimeError(f"script too long: {words} words ≈ {est:.0f}s (max {config.KIDS_MAX_SECONDS}s)")
        if est < config.KIDS_MIN_SECONDS * 0.8:
            raise RuntimeError(f"script too short: {words} words ≈ {est:.0f}s (min {config.KIDS_MIN_SECONDS}s)")
        title = str(script.get("title") or plan["question"])[:100]
        if "like you're 5" not in title.lower():
            title = f"{plan['question'].rstrip('?')}? (Explained Like You're 5)"[:100]
        tags = [str(t) for t in (script.get("tags") or [])][:15]
        if config.KIDS_PLAYLIST and (not tags or tags[0] != config.KIDS_PLAYLIST):
            tags = [config.KIDS_PLAYLIST] + [t for t in tags if t != config.KIDS_PLAYLIST][:14]
        script.update({
            "title": title, "tags": tags, "topic": topic["topic"],
            "thumbnail_text": script.get("thumbnail_text") or plan["question"],
            "analogy": {"world": plan.get("world", ""), "map": plan.get("map", [])},
            "backdrop": getattr(self, "world", {}).get("backdrop", "meadow"),
            "estimated_seconds": round(est), "script_repairs": repairs, "review": reviewed["review"],
            "llm": self.llm.last_model,
        })
        if config.KIDS_SHORTS:
            try:
                short = {"scenes": self.short(script)}
                swap_stand(short, getattr(self, "world", {}).get("place", "stand"))
                script["short"] = short
                logger.info(f"[kids-script] short: {len(short['scenes'])} scenes, {_words(short['scenes'])} words")
            except Exception as e:  # noqa: BLE001 — the renderer falls back to a cut of the full story
                logger.warning(f"[kids-script] short script failed ({str(e)[:120]}) — a cut of the full story is used")
        logger.info(f"[kids-script] ✓ {len(script['scenes'])} scenes, {words} words ≈ {est:.0f}s, "
                    f"{len(repairs)} repairs, checker ok={reviewed['review'].get('ok')}")
        return script
