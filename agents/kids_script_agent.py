"""
Kids script agent: topic → analogy plan → scenes script → checker (+1 fix round) → length guard.

Short videos (≈300 words), so each step is one small free-tier call. Scene problems are
fixed by agents.kids_scene_schema.validate_and_repair, never fatal.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from agents.explainer_script_agent import parse_json_obj
from agents.kids_scene_schema import PROPS, catalogue_for_prompt, validate_and_repair, word_count
from agents.llm import FreeLLM
from agents.packaging import TITLE_MAX, packaging_problems, short_thumb
from agents.script_rules import check_script
from config import config
from templates import kids_prompts as P

REPO = Path(__file__).resolve().parent.parent
TITLE_SUFFIX = " (Explained Like You're 5)"
QUESTION_MAX = TITLE_MAX - len(TITLE_SUFFIX)    # the question that still fits a 60-character title

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


def world_options(area: str = "", history: Optional[List[Dict]] = None, n: int = 4) -> List[Dict]:
    """The `n` worlds used longest ago (never-used first), ones that fit the topic's area first.
    The script model picks the best fit among them, so settings rotate without forcing a world
    onto a topic it does not suit. History rows from before worlds were recorded count as the
    lemonade stand."""
    if history is None:
        try:
            history = json.loads((REPO / config.KIDS_HISTORY_FILE).read_text())
        except Exception:  # noqa: BLE001
            history = []
    used = [h.get("world") or "lemonade stand" for h in history]
    last = {w["key"]: max((i for i, u in enumerate(used) if u == w["key"]), default=-1) for w in WORLDS}
    return sorted(WORLDS, key=lambda w: (last[w["key"]], area not in w["areas"]))[:n]


def pick_world(area: str = "", history: Optional[List[Dict]] = None) -> Dict:
    """Default world when the model does not choose: the first option."""
    return world_options(area, history)[0]


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


FILLER = {"quickly", "perfectly", "cleverly", "brightly", "cheerfully", "smartly", "nicely", "gently", "softly",
          "proudly", "happily", "eagerly", "totally", "really", "today"}


def strip_filler(script: Dict) -> int:
    """Drop a padding word from the end of a line ("says hi cheerfully." → "says hi."). Models add
    these when asked for more words. Lines of five words or fewer are left alone."""
    n = 0
    for sc in script.get("scenes", []):
        for ln in sc.get("lines", []):
            words = str(ln.get("text", "")).split()
            if len(words) < 6:
                continue
            last = words[-1].rstrip(".!?,")
            if last.lower() in FILLER and last.lower() != str(ln.get("cue", "")).lower():
                ln["text"] = " ".join(words[:-1]).rstrip(",;:") + (words[-1][len(last):] or ".")
                n += 1
    return n


def is_hook(text: str) -> bool:
    return text.strip().endswith("?") and len(text.split()) <= 12


def finish_short(scenes: List[Dict], hook: str = "") -> List[Dict]:
    """Shape scenes into a Short: no title card, a question as the first line (the video's own
    question is put in front if the script does not open with one), at most SHORT_MAX_WORDS, and
    a fixed closing line that points to the full video."""
    body = [sc for sc in scenes if isinstance(sc, dict) and sc.get("type") not in ("title", "outro") and sc.get("lines")]
    if hook and body and not is_hook(str(body[0]["lines"][0].get("text", ""))):
        body.insert(0, {"type": "talk", "weather": "sunny", "props": {"who": "mia", "bubble": hook, "prop": "bulb"},
                        "lines": [{"text": hook}]})
    while len(body) > 2 and _words(body) > SHORT_MAX_WORDS - len(SHORT_OUTRO.split()):
        body.pop()
    return body + [{"type": "outro", "weather": "sunny",
                    "props": {"cast": ["leo", "mia", "zoe"], "message": "Watch the full video!"},
                    "lines": [{"text": SHORT_OUTRO}]}]


def short_cut(script: Dict, hook: str = "") -> List[Dict]:
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
    return finish_short(body, hook)


OPENING_WORDS = 35          # ≈ the first 15 s at the kids narration pace
GREETING = re.compile(r"\b(hi|hello|hey|welcome|i'm|i am|my name is|says? (hi|hello)|waves?|waving|"
                      r"appears?|pops? up|bounces? in|walks? in)\b", re.I)


def opening_lines(scenes: List[Dict], words: int = OPENING_WORDS) -> List[Dict]:
    """The narration lines heard in about the first 15 seconds."""
    out, n = [], 0
    for sc in scenes:
        for ln in (sc.get("lines", []) if isinstance(sc, dict) else []):
            if n >= words:
                return out
            out.append(ln)
            n += len(str(ln.get("text", "")).split())
    return out


def opening_problems(scenes: List[Dict]) -> List[str]:
    """Why the first 15 seconds would lose a viewer: no question first, a greeting or a described
    picture where the story should start, or nothing said to the viewer."""
    lines = [str(ln.get("text", "")) for ln in opening_lines(scenes)]
    if not lines:
        return []
    out = []
    if not lines[0].strip().endswith("?"):
        out.append("the first line must be the question")
    for t in lines[1:]:
        m = GREETING.search(t)
        if m:
            out.append(f'"{t}" greets or describes the picture ("{m.group(0)}"); start the story\'s problem instead')
    if not re.search(r"\byou(r|'ll)?\b", " ".join(lines[1:]), re.I):
        out.append('one of the first lines must tell the viewer what they will understand, using "you"')
    return out


def drop_greetings(scenes: List[Dict]) -> int:
    """Last resort when the model keeps greeting: cut those lines from the opening. A scene always
    keeps one line, and the first line (the question) is never cut."""
    n = 0
    for ln in opening_lines(scenes)[1:]:
        if not GREETING.search(str(ln.get("text", ""))):
            continue
        sc = next(s for s in scenes if isinstance(s, dict) and any(x is ln for x in s.get("lines", [])))
        if len(sc["lines"]) > 1:
            sc["lines"] = [x for x in sc["lines"] if x is not ln]
            n += 1
    return n


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
        tries = 0

        def check(o):
            nonlocal tries
            tries += 1
            q = str(o.get("question", "")).strip()
            if not q:
                raise ValueError("missing question")
            if len(q) > QUESTION_MAX and tries <= 2:
                raise ValueError(f'"question" has {len(q)} characters; write it in {QUESTION_MAX} or fewer')
            if not isinstance(o.get("map"), list) or not o["map"]:
                raise ValueError("missing map")
            if not isinstance(o.get("story"), list) or len(o["story"]) < 4:
                raise ValueError("story needs 4+ beats")

        ctx = "\n".join(x for x in (topic.get("from_headline", ""), topic.get("summary", ""), topic.get("hint", "")) if x)
        opts = world_options(topic.get("area", ""))
        worlds = "\n".join(f'  - key "{w["key"]}": {w["world"]}. Main place: prop "{w["place"]}" with the sign '
                           f'"{w["label"]}". Things that fit: {w["items"]}.' for w in opts)
        plan = self._ask(P.PLAN_USER.format(question=topic["topic"], context=ctx or "(none)", props=", ".join(PROPS),
                                            worlds=worlds), check, max_tokens=3000)
        key = str(plan.get("world_key", "")).strip().lower()
        w = next((o for o in opts if o["key"] == key), opts[0])
        self.world = w
        topic["world"] = w["key"]   # recorded in the history by mark_used after a successful upload
        logger.info(f"[kids-script] story world: {w['world']} (options: {', '.join(o['key'] for o in opts)})")
        return plan

    def write(self, plan: Dict) -> Dict:
        lo, hi = word_bounds()

        tries = 0

        def check(o):
            nonlocal tries
            tries += 1
            if not isinstance(o.get("scenes"), list) or len(o["scenes"]) < 5:
                raise ValueError("need 5+ scenes")
            validate_and_repair(o)
            bad = opening_problems(o["scenes"])
            if bad and tries <= 2:   # ask twice for a better opening, then take what there is
                raise ValueError("weak opening: " + "; ".join(bad))
            bad = [p for p in packaging_problems(str(plan.get("question", "")), str(o.get("thumbnail_text", "")))
                   if "thumbnail" in p]
            if bad and tries <= 2:
                raise ValueError("; ".join(bad))

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
        rules = [p for p in check_script(script) if "title has" not in p]   # the title is rebuilt later
        if (verdict.get("ok") or not problems) and not rules:
            return {"script": script, "review": {"ok": True, "problems": problems}}
        if verdict.get("ok"):
            problems = []
        problems += rules
        logger.info(f"[kids-script] checker: {len(problems) - len(rules)} problem(s), script rules: {len(rules)} — one fix round")
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
        tries = 0

        def check(o):
            nonlocal tries
            tries += 1
            if not isinstance(o.get("scenes"), list) or len(o["scenes"]) < 3:
                raise ValueError("need 3+ scenes")
            w = _words([sc for sc in o["scenes"] if isinstance(sc, dict)])
            if w < 40:
                raise ValueError(f"only {w} words, need {SHORT_WORDS[0]}-{SHORT_WORDS[1]}")
            first = next((sc for sc in o["scenes"] if isinstance(sc, dict) and sc.get("type") != "title" and sc.get("lines")), {})
            if not is_hook(str((first.get("lines") or [{}])[0].get("text", ""))):
                raise ValueError('the first line must be a question of at most 10 words ending in "?"')
            body = [sc for sc in o["scenes"] if isinstance(sc, dict) and sc.get("type") != "title"]
            bad = [p for p in opening_problems(body) if "greets" in p]
            if bad and tries <= 2:
                raise ValueError("weak opening: " + "; ".join(bad))

        full = {"title": script.get("title", ""), "scenes": script.get("scenes", [])}
        o = self._ask(P.SHORT_USER.format(script=json.dumps(full, ensure_ascii=False), min_words=SHORT_WORDS[0],
                                          max_words=SHORT_WORDS[1], catalogue=catalogue_for_prompt()),
                      check, max_tokens=6000, repairs=2)
        scenes = finish_short(o["scenes"])
        drop_greetings(scenes)
        return scenes

    def generate(self, topic: Dict) -> Dict:
        logger.info(f"[kids-script] topic: {topic['topic'][:70]}")
        plan = self.plan(topic)
        logger.info(f"[kids-script] analogy: {plan.get('world', '')!r} — {len(plan.get('map', []))} grown-up words")
        script = self.write(plan)
        script = self.fit_length(script)
        reviewed = self.review(script)
        script = reviewed["script"]
        script, repairs = validate_and_repair(script)
        cut = drop_greetings(script["scenes"])
        if cut:
            logger.info(f"[kids-script] cut {cut} greeting line(s) from the opening")
        logger.info("[kids-script] opening: " + " / ".join(str(ln["text"]) for ln in opening_lines(script["scenes"])))
        for p in opening_problems(script["scenes"]):
            logger.warning(f"[kids-script] opening still weak: {p}")
        trimmed = strip_filler(script)
        if trimmed:
            logger.info(f"[kids-script] removed a padding word from {trimmed} line(s)")
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
        if "like you're 5" not in title.lower() or len(title) > TITLE_MAX:
            title = f"{plan['question'].rstrip('?')}?{TITLE_SUFFIX}"[:100]
        thumb = str(script.get("thumbnail_text") or "").strip()
        if not thumb or len(thumb.split()) > 3:
            thumb = short_thumb(plan["question"])
        script["thumbnail_text"] = thumb
        for p in packaging_problems(title, thumb):
            logger.warning(f"[kids-script] packaging: {p}")
        tags = [str(t) for t in (script.get("tags") or [])][:15]
        if config.KIDS_PLAYLIST and (not tags or tags[0] != config.KIDS_PLAYLIST):
            tags = [config.KIDS_PLAYLIST] + [t for t in tags if t != config.KIDS_PLAYLIST][:14]
        script.update({
            "title": title, "tags": tags, "topic": topic["topic"],
            "analogy": {"world": plan.get("world", ""), "map": plan.get("map", [])},
            "backdrop": getattr(self, "world", {}).get("backdrop", "meadow"),
            "estimated_seconds": round(est), "script_repairs": repairs, "review": reviewed["review"],
            "llm": self.llm.last_model,
        })
        if config.KIDS_SHORTS:
            try:
                short = {"scenes": self.short(script)}
                strip_filler(short)
                swap_stand(short, getattr(self, "world", {}).get("place", "stand"))
                script["short"] = short
                logger.info(f"[kids-script] short: {len(short['scenes'])} scenes, {_words(short['scenes'])} words")
            except Exception as e:  # noqa: BLE001 — the renderer falls back to a cut of the full story
                logger.warning(f"[kids-script] short script failed ({str(e)[:120]}) — a cut of the full story is used")
        script["rule_problems"] = check_script(script)
        for p in script["rule_problems"]:
            logger.warning(f"[kids-script] rule still broken: {p}")
        logger.info(f"[kids-script] ✓ {len(script['scenes'])} scenes, {words} words ≈ {est:.0f}s, "
                    f"{len(repairs)} repairs, checker ok={reviewed['review'].get('ok')}")
        return script
