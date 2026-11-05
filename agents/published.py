"""
Titles of every video already on the channel (public, private, unlisted and scheduled), read with
the channel's own sign-in, so no topic is made twice. Topic history only starts on 2026-09-30 and
the explainer history drops entries after 90 days; the channel itself is the full record.

No token (local runs, tests) or an API error → an empty list, and the history checks still apply.
"""

import logging
import os
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

_cache: Optional[List[str]] = None
KIDS_SUFFIX = re.compile(r"\s*(\(Explained Like You're 5\)|\|\s*Explained Like You're 5).*$", re.I)


def channel_titles() -> List[str]:
    global _cache
    if _cache is not None:
        return _cache
    _cache = []
    if not os.getenv("YOUTUBE_TOKEN_JSON"):
        return _cache
    try:
        from agents.upload_agent import UploadAgent
        from scripts.link_comments import channel_uploads
        _, videos = channel_uploads(UploadAgent().youtube, limit=500)
        _cache = [v["title"] for v in videos]
        logger.info(f"[published] {len(_cache)} videos already on the channel")
    except Exception as e:  # noqa: BLE001 — the history checks still apply
        logger.warning(f"[published] could not list the channel's videos ({str(e)[:150]})")
    return _cache


def kids_questions(titles: List[str]) -> List[str]:
    """'How does AI learn? | Explained Like You're 5 #Shorts' → 'How does AI learn?'."""
    return sorted({KIDS_SUFFIX.sub("", t).strip() for t in titles if "explained like you" in t.lower()})


def alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def explainer_subject(topic: str) -> str:
    """The thing a bank topic is about: 'Open WebUI with Ollama: a private…' → 'openwebui';
    'Mixture of Experts explained: why…' → 'mixtureofexperts'. Empty when there is no clear name."""
    head = topic.split(":")[0] if ":" in topic else ""
    head = re.sub(r"\s+(with|on|in|for)\s+.*$", "", head, flags=re.I)
    head = re.sub(r"\s+explained$", "", head.strip(), flags=re.I)
    return alnum(head)


def explainer_published(topic: str, titles: List[str]) -> bool:
    """True when a published (non-kids) title already names this topic's subject."""
    subject = explainer_subject(topic)
    if len(subject) < 3:
        return False
    return any(subject in alnum(t) for t in titles if "explained like you" not in t.lower())
