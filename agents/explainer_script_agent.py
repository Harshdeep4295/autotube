"""
Explainer script agent (Phase A): topic → grounded script with shots + scene specs.

Outline call, then one call per chapter (small requests fit free-tier limits and
keep each response well-formed). Invalid JSON gets one repair round-trip; scene
problems are fixed by agents.scene_schema.validate_and_repair, never fatal.
"""

import json
import logging
import re
from typing import Dict, List, Optional

from agents.fact_check import unsupported_numbers
from agents.llm import FreeLLM
from agents.scene_schema import ICONS, catalogue_for_prompt, validate_and_repair
from agents.source_fetcher import fetch_text
from config import config
from templates import explainer_prompts as P

logger = logging.getLogger(__name__)

WORDS_PER_SHOT = 19          # prompt asks for 16-24 words per shot
CHAPTER_MIN_SHARE = 0.95     # top a chapter up until it has 95% of its target words
CHAPTER_REPAIRS = 2          # re-asks for unusable (non-JSON) chapter answers
CHAPTER_TOPUPS = 3           # continuation calls for a chapter that came out short
TOPUP_OVERASK = 1.5          # models under-deliver, so ask for 1.5x the missing words
CHAPTER_MAX_TOKENS = 12000


def parse_json_obj(text: str) -> Dict:
    """Parse the first JSON object in a model response (tolerates ``` fences and chatter)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        start = t.find("{")
        if start < 0:
            raise ValueError("no JSON object in response")
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(t[start:], start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    obj = json.loads(t[start:i + 1])
                    break
        else:
            raise ValueError("unterminated JSON object in response")
    if isinstance(obj, list):
        # Small models sometimes answer with a bare list: [ {...outline...} ] or [ shot, shot, ... ].
        dicts = [x for x in obj if isinstance(x, dict)]
        if len(dicts) == 1 and len(obj) == 1:
            obj = dicts[0]
        elif dicts and all("text" in d for d in dicts):
            obj = {"shots": dicts}
    if not isinstance(obj, dict):
        raise ValueError("response JSON is not an object")
    return obj


def salvage_shots(text: str) -> List[Dict]:
    """Complete shot objects from a truncated `{"shots": [ ... ` answer (cut off by the token limit)."""
    i = text.find('"shots"')
    i = text.find("[", i) if i >= 0 else -1
    if i < 0:
        return []
    shots, depth, in_str, esc, start = [], 0, False, False, None
    for j in range(i + 1, len(text)):
        ch = text[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = j
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    o = json.loads(text[start:j + 1])
                    if isinstance(o, dict) and o.get("text"):
                        shots.append(o)
                except json.JSONDecodeError:
                    pass
                start = None
        elif ch == "]" and depth == 0:
            break
    return shots


def estimated_seconds(words: int) -> float:
    """Narration length estimate (Kokoro at KOKORO_SPEED, pauses included ≈ EXPLAINER_WPM)."""
    return words / max(60, config.EXPLAINER_WPM) * 60


def word_count(shots: List[Dict]) -> int:
    return sum(len(str(s.get("text", "")).split()) for s in shots)


class ExplainerScriptAgent:
    def __init__(self, llm: Optional[FreeLLM] = None):
        self.llm = llm or FreeLLM()
        self.system = P.SYSTEM.format(subniche=config.CHANNEL_SUBNICHE)

    def _ask(self, user: str, check, max_tokens: int = 6000, repairs: int = 2) -> Dict:
        """One call + up to `repairs` repair round-trips. `check(obj)` raises ValueError if unusable."""
        prompt = user
        for attempt in range(repairs + 1):
            text = self.llm.complete(self.system, prompt, max_tokens=max_tokens)
            try:
                obj = parse_json_obj(text)
                check(obj)
                return obj
            except ValueError as e:
                if attempt == repairs:
                    raise
                logger.warning(f"[script] unusable response ({e}) — asking for a repair")
                prompt = user + "\n\n" + P.REPAIR_USER.format(error=str(e)[:300])
        raise ValueError("unreachable")

    def source_for(self, topic: Dict) -> str:
        text = fetch_text(topic.get("url", ""))
        if len(text) < 400:
            text = "\n".join(x for x in (topic.get("topic", ""), topic.get("summary", ""), text) if x)
        return text[:6000]

    def outline(self, topic: Dict, source: str) -> Dict:
        words = config.EXPLAINER_TARGET_WORDS

        def check(o):
            if not isinstance(o.get("chapters"), list) or not 3 <= len(o["chapters"]) <= 8:
                raise ValueError("need 3-8 chapters")
            if not str(o.get("title", "")).strip():
                raise ValueError("missing title")

        user = P.OUTLINE_USER.format(minutes=round(words / config.EXPLAINER_WPM), words=words, topic=topic["topic"],
                                     source=source or "(no source text available — use only general knowledge)",
                                     icons=", ".join(ICONS))
        o = self._ask(user, check, max_tokens=6000)
        total = sum(int(c.get("target_words") or 0) for c in o["chapters"]) or words
        for c in o["chapters"]:  # rescale so chapters add up to the target length
            c["target_words"] = max(60, round(int(c.get("target_words") or words / len(o["chapters"])) * words / total))
        return o

    def chapter(self, outline: Dict, idx: int, source: str, previous: List[str]) -> List[Dict]:
        """Shots for one chapter. Small free models often write about half the requested
        length, so a short answer is topped up with continuation calls instead of failing
        the whole video; cut-off JSON is salvaged shot by shot."""
        chs = outline["chapters"]
        ch = chs[idx]
        target = int(ch["target_words"])
        n_shots = max(4, round(target / WORDS_PER_SHOT))
        position = P.FIRST_RULE if idx == 0 else P.LAST_RULE if idx == len(chs) - 1 else P.MIDDLE_RULE
        base = dict(
            index=idx + 1, count=len(chs), title=outline["title"],
            chapter_titles=" | ".join(c.get("title", "") for c in chs), chapter_title=ch.get("title", ""),
            goal=ch.get("goal", ""), key_points="; ".join(map(str, ch.get("key_points", []))),
            source=source or "(no source text — general knowledge only)", catalogue=catalogue_for_prompt(),
            position_rule=position,
        )
        user = P.CHAPTER_USER.format(**base, target_words=target, n_shots=n_shots,
                                     previous=" ".join(previous[-2:]) or "(start of video)")

        shots: List[Dict] = []
        error = ""
        for attempt in range(1 + CHAPTER_REPAIRS):
            prompt = user if attempt == 0 else user + "\n\n" + P.REPAIR_USER.format(error=error[:300])
            text = self.llm.complete(self.system, prompt, max_tokens=CHAPTER_MAX_TOKENS)
            try:
                got = parse_json_obj(text).get("shots")
                if not isinstance(got, list):
                    raise ValueError("missing 'shots' list")
                got = [x for x in got if isinstance(x, dict) and str(x.get("text", "")).strip()]
            except ValueError as e:
                got = salvage_shots(text)
                if got:
                    logger.warning(f"[script] chapter {idx+1}: salvaged {len(got)} shots from a cut-off answer ({e})")
                else:
                    error = str(e)
                    logger.warning(f"[script] chapter {idx+1}: unusable response ({e}) — asking for a repair")
                    continue
            if word_count(got) > word_count(shots):
                shots = got
            if word_count(shots) >= target * CHAPTER_MIN_SHARE:
                break
            error = (f"only {word_count(shots)} words in {len(shots)} shots — write {n_shots} shots "
                     f"of 16-24 words each (about {target} words)")
            logger.warning(f"[script] chapter {idx+1}: {error}")
            break   # a valid but short answer is topped up below instead of rewritten
        if not shots:
            raise ValueError(f"chapter {idx+1}: no usable shots ({error})")

        for _ in range(CHAPTER_TOPUPS):
            have = word_count(shots)
            if have >= target * CHAPTER_MIN_SHARE:
                break
            missing = target - have
            ask = round(missing * TOPUP_OVERASK)
            more_shots = max(2, round(ask / WORDS_PER_SHOT))
            cont = P.CONTINUE_USER.format(**base, missing_words=ask, n_shots=more_shots,
                                          so_far=" ".join(str(x.get("text", "")) for x in shots))
            try:
                text = self.llm.complete(self.system, cont, max_tokens=CHAPTER_MAX_TOKENS)
                try:
                    extra = parse_json_obj(text).get("shots") or []
                except ValueError:
                    extra = salvage_shots(text)
            except Exception as e:  # noqa: BLE001 — keep what we have
                logger.warning(f"[script] chapter {idx+1}: top-up failed ({str(e)[:120]})")
                break
            extra = [x for x in extra if isinstance(x, dict) and str(x.get("text", "")).strip()]
            if not extra:
                break
            if idx == len(chs) - 1 and shots and (shots[-1].get("scene") or {}).get("type") == "cta_end":
                shots = shots[:-1] + extra + shots[-1:]   # keep the comment question last
            else:
                shots += extra
            logger.info(f"[script] chapter {idx+1}: topped up +{len(extra)} shots → {word_count(shots)} words")

        if word_count(shots) < target * 0.5:
            raise ValueError(f"chapter {idx+1}: only {word_count(shots)} words, need about {target}")
        shots[0]["chapter"] = ch.get("title", "")
        return shots

    def generate(self, topic: Dict) -> Dict:
        source = self.source_for(topic)
        logger.info(f"[script] topic: {topic['topic'][:70]} (source text: {len(source)} chars)")
        outline = self.outline(topic, source)
        shots: List[Dict] = []
        for i in range(len(outline["chapters"])):
            new = self.chapter(outline, i, source, [s.get("text", "") for s in shots if isinstance(s, dict)])
            shots += new
            logger.info(f"[script] chapter {i+1}/{len(outline['chapters'])}: {len(new)} shots, {word_count(new)} words")

        script = {
            "title": str(outline["title"])[:100],
            "description": outline.get("description", ""),
            "tags": [str(t) for t in outline.get("tags", [])][:15],
            "thumbnail_text": outline.get("thumbnail_text", ""),
            "thumbnail_subtext": outline.get("thumbnail_subtext", ""),
            "thumbnail_icon": outline.get("thumbnail_icon", "lightbulb") if outline.get("thumbnail_icon") in ICONS else "lightbulb",
            "sources": [{"title": topic["topic"], "url": topic.get("url", "")}] if topic.get("url") else [],
            "topic": topic["topic"],
            "shots": shots,
        }
        script, repairs = validate_and_repair(script)
        words = word_count(script["shots"])
        est = estimated_seconds(words)
        script["estimated_seconds"] = round(est)
        if words < config.EXPLAINER_TARGET_WORDS * 0.75 or est < config.EXPLAINER_MIN_SECONDS:
            raise RuntimeError(f"script too short: {words} words ≈ {est/60:.1f} min at {config.EXPLAINER_WPM} wpm "
                               f"(need ≥ {config.EXPLAINER_MIN_SECONDS/60:.0f} min; target {config.EXPLAINER_TARGET_WORDS} words)")
        script["fact_flags"] = unsupported_numbers(script, source)
        script["script_repairs"] = repairs
        script["llm"] = self.llm.last_model
        logger.info(f"[script] ✓ {len(script['shots'])} shots, {words} words, {len(repairs)} repairs, "
                    f"{len(script['fact_flags'])} numbers not found in source, ≈ {est/60:.1f} min")
        return script
