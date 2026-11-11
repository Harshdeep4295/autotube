"""
Is a new topic the same video as one already made? One check for every place a topic is picked
(kids picker, explainer bank / plan / news, weekly planner).

  1. score >= the hard line (TOPIC_DUP_SIMILARITY / EXPLAINER_DUP_SIMILARITY): a repeat, no question.
  2. score in the grey zone (from KIDS_JUDGE_FROM / EXPLAINER_JUDGE_FROM): a score alone cannot tell
     "Why do prices jump up?" vs "Why do things cost more?" (0.77, a repeat) from "Why do house prices
     change?" (0.79, a different video), so an AI reads the closest past topics and decides. Claude on
     the owner's subscription when the CLI is there, else the free models; no answer → not a repeat
     (the word rules and the hard line still apply).
  3. below that: new.

    from agents.topic_judge import same_as
    hit = same_as("Why do prices jump up?", past_topics, "kids")   # → (0.77, "Why do things cost more?") or None
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from agents import topic_index
from config import config

logger = logging.getLogger(__name__)

NEIGHBOURS = 6
_cache: Dict[Tuple[str, str, Tuple[str, ...]], Optional[str]] = {}

RULES = {
    "kids": (
        "The channel makes one short video per question for young children (\"Explained Like You're 5\").\n"
        "SAME video: the same core idea asked in other words, so a parent who saw the old one would say "
        "\"they already did this\". Examples: \"Why do prices jump up?\" = \"Why do things cost more?\"; "
        "\"How does AI get smarter?\" = \"How does AI learn?\"; \"What is a computer chip?\" = \"What is a Chip?\".\n"
        "DIFFERENT video: a different specific thing or a different idea, even in the same area. Examples: "
        "\"Why does gasoline cost so much?\" vs \"Why do house prices change?\"; \"How does AI learn?\" vs "
        "\"Why does AI need rules?\"; \"Why do we pay taxes?\" vs \"Why do people save money?\"."
    ),
    "explainer": (
        "The channel makes one explainer per tool, model or idea about running AI on your own computer.\n"
        "SAME video: the same tool, the same model version or the same concept, whatever the wording. "
        "Examples: \"Install Ollama on Windows\" = \"Run Ollama locally\"; \"Quantization explained\" = "
        "\"How big models fit on small GPUs with quantization\".\n"
        "DIFFERENT video: a different tool even if it does a similar job (\"Jan\" vs \"Open WebUI\", "
        "\"whisper.cpp\" vs \"faster-whisper\"), a new version of a model (\"Qwen 3.6\" vs \"Qwen 3.5\"), "
        "or a different concept (\"Quantization\" vs \"Mixture of Experts\")."
    ),
}

PROMPT = """{rules}

NEW topic: {new}

Already made:
{past}

Is the NEW topic the same video as one already made? Reply with JSON only:
{{"same": <the number of the matching video, or 0 if none is the same>, "why": "<a few words>"}}"""


def _ask(prompt: str) -> Optional[str]:
    from agents import claude_writer
    try:
        if claude_writer.available():
            return claude_writer.ask(prompt, timeout=240, model=config.TOPIC_JUDGE_MODEL)
        from agents.llm import FreeLLM
        return FreeLLM().complete("You compare video topics. Reply with JSON only.", prompt,
                                  max_tokens=300, temperature=0.0)
    except Exception as e:  # noqa: BLE001 — no judge: the hard line and the word rules still apply
        logger.warning(f"[judge] no answer ({str(e)[:150]})")
        return None


def judge(new: str, candidates: List[str], track: str) -> Optional[str]:
    """The candidate the AI says is the same video as `new`, or None (also when it cannot answer)."""
    if not candidates:
        return None
    key = (track, new, tuple(candidates))
    if key in _cache:
        return _cache[key]
    past = "\n".join(f"{i}. {c}" for i, c in enumerate(candidates, 1))
    text = _ask(PROMPT.format(rules=RULES[track], new=new, past=past))
    verdict = None
    if text:
        m = re.search(r"\{.*\}", text, re.S)
        try:
            n = int(json.loads(m.group(0)).get("same") or 0) if m else 0
        except (ValueError, TypeError, json.JSONDecodeError):
            n = 0
        if 1 <= n <= len(candidates):
            verdict = candidates[n - 1]
    _cache[key] = verdict
    return verdict


def same_as(new: str, past: List[str], track: str) -> Optional[Tuple[float, str]]:
    """(similarity, past topic) when `new` is the same video as something in `past`, else None."""
    hard = config.TOPIC_DUP_SIMILARITY if track == "kids" else config.EXPLAINER_DUP_SIMILARITY
    grey = config.KIDS_JUDGE_FROM if track == "kids" else config.EXPLAINER_JUDGE_FROM
    near = topic_index.similar(new, past, k=NEIGHBOURS)
    if not near:
        return None
    if near[0][0] >= hard:
        return near[0]
    close = [n for n in near if n[0] >= grey]
    if not close or not config.TOPIC_JUDGE:
        return None
    hit = judge(new, [c[1] for c in close], track)
    if hit:
        score = next(s for s, c in close if c == hit)
        logger.info(f"[judge] '{new[:60]}' is the same video as '{hit[:60]}' ({score:.2f})")
        return score, hit
    return None


def reset() -> None:
    _cache.clear()
