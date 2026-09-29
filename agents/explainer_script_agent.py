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
    if not isinstance(obj, dict):
        raise ValueError("response JSON is not an object")
    return obj


def word_count(shots: List[Dict]) -> int:
    return sum(len(str(s.get("text", "")).split()) for s in shots)


class ExplainerScriptAgent:
    def __init__(self, llm: Optional[FreeLLM] = None):
        self.llm = llm or FreeLLM()
        self.system = P.SYSTEM.format(subniche=config.CHANNEL_SUBNICHE)

    def _ask(self, user: str, check, max_tokens: int = 6000) -> Dict:
        """One call + at most one repair round-trip. `check(obj)` raises ValueError if unusable."""
        text = self.llm.complete(self.system, user, max_tokens=max_tokens)
        try:
            obj = parse_json_obj(text)
            check(obj)
            return obj
        except ValueError as e:
            logger.warning(f"[script] unusable response ({e}) — asking for a repair")
            text = self.llm.complete(self.system, user + "\n\n" + P.REPAIR_USER.format(error=str(e)[:300]),
                                     max_tokens=max_tokens)
            obj = parse_json_obj(text)
            check(obj)
            return obj

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

        user = P.OUTLINE_USER.format(minutes=round(words / 140), words=words, topic=topic["topic"],
                                     source=source or "(no source text available — use only general knowledge)",
                                     icons=", ".join(ICONS))
        o = self._ask(user, check, max_tokens=3000)
        total = sum(int(c.get("target_words") or 0) for c in o["chapters"]) or words
        for c in o["chapters"]:  # rescale so chapters add up to the target length
            c["target_words"] = max(60, round(int(c.get("target_words") or words / len(o["chapters"])) * words / total))
        return o

    def chapter(self, outline: Dict, idx: int, source: str, previous: List[str]) -> List[Dict]:
        chs = outline["chapters"]
        ch = chs[idx]
        target = int(ch["target_words"])
        position = P.FIRST_RULE if idx == 0 else P.LAST_RULE if idx == len(chs) - 1 else P.MIDDLE_RULE

        def check(o):
            shots = o.get("shots")
            if not isinstance(shots, list) or not shots:
                raise ValueError("missing 'shots' list")
            if word_count(shots) < target * 0.5:
                raise ValueError(f"only {word_count(shots)} words, need about {target}")

        user = P.CHAPTER_USER.format(
            index=idx + 1, count=len(chs), title=outline["title"],
            chapter_titles=" | ".join(c.get("title", "") for c in chs), chapter_title=ch.get("title", ""),
            goal=ch.get("goal", ""), key_points="; ".join(map(str, ch.get("key_points", []))),
            target_words=target, min_shots=max(3, target // 16), max_shots=max(5, target // 8),
            position_rule=position, previous=" ".join(previous[-2:]) or "(start of video)",
            source=source or "(no source text — general knowledge only)", catalogue=catalogue_for_prompt(),
        )
        shots = self._ask(user, check)["shots"]
        if shots and isinstance(shots[0], dict):
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
        if words < config.EXPLAINER_TARGET_WORDS * 0.75:
            raise RuntimeError(f"script too short: {words} words (target {config.EXPLAINER_TARGET_WORDS})")
        script["fact_flags"] = unsupported_numbers(script, source)
        script["script_repairs"] = repairs
        script["llm"] = self.llm.last_model
        logger.info(f"[script] ✓ {len(script['shots'])} shots, {words} words, {len(repairs)} repairs, "
                    f"{len(script['fact_flags'])} numbers not found in source")
        return script
