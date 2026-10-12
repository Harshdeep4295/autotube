"""
Title + thumbnail checks shared by both tracks. The two are one unit: search cuts a title near
60 characters, a thumbnail holds about three words at feed size, and a thumbnail that repeats
the title wastes half of what the viewer sees before clicking.
"""

import re
from typing import List

TITLE_MAX = 60
THUMB_MAX_WORDS = 3
STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are", "with", "your", "you", "my",
        "i", "this", "that", "it", "how", "what", "why", "do", "does", "so", "like", "explained", "you're"}


def content_words(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9']+", str(text).lower()) if w not in STOP and len(w) > 1]


def packaging_problems(title: str, thumb: str, thumb_words: int = THUMB_MAX_WORDS) -> List[str]:
    out = []
    if len(title) > TITLE_MAX:
        out.append(f"the title has {len(title)} characters; the limit is {TITLE_MAX}")
    n = len(str(thumb).split())
    if n > thumb_words:
        out.append(f"thumbnail_text has {n} words; the limit is {thumb_words}")
    shared = sorted(set(content_words(title)) & set(content_words(thumb)))
    if len(shared) >= 2:
        out.append(f"thumbnail_text repeats the title ({', '.join(shared)}); use different words for the same promise")
    return out


def short_thumb(text: str, words: int = THUMB_MAX_WORDS) -> str:
    """Fallback when the model keeps writing a long thumbnail: the first few content words."""
    keep = [w for w in re.findall(r"[A-Za-z0-9']+", str(text)) if w.lower() not in STOP][:words]
    return " ".join(keep) + ("?" if str(text).strip().endswith("?") and keep else "")
