"""
Daily trend check for the explainer: the newest open AI model people are excited about right now.

Videos that break out in this niche name something released days ago ("Run X Locally", "Can you
run X at home?"), so before falling back to the evergreen topic bank, each run looks at Hugging
Face's trending models (free, no key) and takes the strongest one that is:
  - an original release (not a quantized / uncensored / GGUF copy made by someone else),
  - at most TREND_MAX_AGE_DAYS old,
  - liked by at least TREND_MIN_LIKES people,
  - not covered before (its family name is not in the explainer history).
Well-known labs rank first: their names are what people search for.
The model card is the source text the script is checked against.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from config import config

logger = logging.getLogger(__name__)

HF_TRENDING = ("https://huggingface.co/api/models?sort=trendingScore&limit=60"
               "&expand[]=createdAt&expand[]=likes&expand[]=trendingScore&expand[]=pipeline_tag&expand[]=cardData")

# Labs whose names people search for. Unknown authors still count, ranked lower.
KNOWN_LABS = {
    "deepseek-ai", "qwen", "meta-llama", "google", "mistralai", "microsoft", "nvidia", "openai",
    "black-forest-labs", "lightricks", "stabilityai", "liquidai", "baidu", "tencent", "minimaxai",
    "moonshotai", "zai-org", "thudm", "ibm-granite", "apple", "allenai", "huggingfacetb", "opengvlab",
    "bytedance", "bytedance-seed", "wan-ai", "openbmb", "fishaudio", "hexgrad", "xai-org", "ai21labs",
    "cohereforai", "coherelabs", "facebook", "amazon", "salesforce", "internlm", "stepfun-ai", "kwai-kolors",
}
COPY_WORDS = re.compile(r"gguf|awq|gptq|exl2|mlx|abliterat|uncensored|quantized|heretic|-int4|-int8|-nf4", re.I)

WHAT = {
    "text-generation": "AI language model",
    "image-text-to-text": "AI model that reads images and text",
    "text-to-image": "AI image generator",
    "image-to-image": "AI image editor",
    "image-to-video": "AI video generator",
    "text-to-video": "AI video generator",
    "text-to-speech": "AI voice model",
    "automatic-speech-recognition": "speech-to-text model",
    "translation": "AI translation model",
    "any-to-any": "AI model for text, images and audio",
    "feature-extraction": "AI embedding model",
    "mask-generation": "AI image cut-out model",
}


def family(model_id: str) -> str:
    """'deepseek-ai/DeepSeek-V4.1-Flash-1017' → 'deepseek v41 flash': the name without author,
    date stamps or size suffixes, so a re-release of the same model is not covered twice."""
    name = model_id.split("/")[-1].lower()
    name = re.sub(r"[-_.]?(\d{4}|\d{6,8})$", "", name)            # date stamps like -1017
    name = re.sub(r"[-_](base|instruct|chat|it|hf|diffusers|comfy)$", "", name)
    return re.sub(r"[^a-z0-9]+", " ", name.replace(".", "")).strip()


def is_original(m: Dict) -> bool:
    """Released by its own lab, not a copy of someone else's model."""
    if COPY_WORDS.search(m.get("id", "")):
        return False
    author = m.get("id", "").split("/")[0].lower()
    base = (m.get("cardData") or {}).get("base_model")
    bases = base if isinstance(base, list) else [base] if base else []
    return all(str(b).split("/")[0].lower() == author for b in bases)


def age_days(m: Dict, now: Optional[datetime] = None) -> float:
    try:
        made = datetime.fromisoformat(str(m["createdAt"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return 1e9
    return ((now or datetime.now(timezone.utc)) - made).total_seconds() / 86400


def covered(model_id: str, history: List[Dict]) -> bool:
    fam = family(model_id)
    if not fam:
        return True
    for h in history:
        text = re.sub(r"[^a-z0-9]+", " ", str(h.get("topic", "")).lower().replace(".", ""))
        if f" {fam} " in f" {text} ":
            return True
    return False


def rank(models: List[Dict], history: List[Dict], now: Optional[datetime] = None) -> List[Dict]:
    keep = [m for m in models
            if is_original(m) and m.get("pipeline_tag") in WHAT
            and age_days(m, now) <= config.TREND_MAX_AGE_DAYS
            and int(m.get("likes") or 0) >= config.TREND_MIN_LIKES
            and not covered(m["id"], history)]
    known = lambda m: m["id"].split("/")[0].lower() in KNOWN_LABS
    return sorted(keep, key=lambda m: (not known(m), -float(m.get("trendingScore") or 0)))


def to_topic(m: Dict) -> Dict:
    name = m["id"].split("/")[-1]
    what = WHAT.get(m.get("pipeline_tag", ""), "AI model")
    return {
        "topic": f"{name}: the new {what} from {m['id'].split('/')[0]}, and can you run it at home?",
        "kind": "trend",
        "source": "trend",
        "summary": f"Trending on Hugging Face now ({m.get('likes')} likes, released {str(m.get('createdAt'))[:10]}).",
        "url": f"https://huggingface.co/{m['id']}",
        "source_url": f"https://huggingface.co/{m['id']}/raw/main/README.md",
    }


def trending_topic(history: List[Dict]) -> Optional[Dict]:
    """Today's trend topic, or None (feed down, or nothing new and strong enough)."""
    try:
        r = requests.get(HF_TRENDING, timeout=20, headers={"User-Agent": "AutoTube/1.0"})
        r.raise_for_status()
        models = r.json()
    except Exception as e:  # noqa: BLE001 — the topic bank is the fallback
        logger.warning(f"[trends] Hugging Face trending unavailable: {str(e)[:120]}")
        return None
    ranked = rank(models, history)
    for m in ranked[:5]:
        logger.info(f"[trends] candidate {m['id']} ({m.get('likes')} likes, {age_days(m):.0f} days old)")
    if not ranked:
        logger.info("[trends] nothing new and strong enough today — using the topic bank")
        return None
    return to_topic(ranked[0])
