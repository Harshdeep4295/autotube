"""
Kids topic agent: today's finance/tech headlines → the evergreen idea behind them
("RBI cuts repo rate" → "What is interest?"), with a curated bank as fallback.

Modes (KIDS_TOPIC_MODE): mixed (default) = headline ideas first, bank fallback;
feed = headlines only; bank = bank only. Areas follow KIDS_AREA_CYCLE day by day
(default ai, tech, ai, finance: AI ideas lead viewers on to the explainers).
Topics are recorded in KIDS_HISTORY_FILE only after a successful upload (mark_used).
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)
REPO = Path(__file__).resolve().parent.parent

DEFAULT_FEEDS = (
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.theverge.com/rss/index.xml",
    "https://techcrunch.com/feed/",
)
BLOCK = re.compile(r"\b(war|kill|dead|death|shoot|attack|crash|murder|abuse|bomb|terror|suicide|crime|arrest)\w*", re.I)


STOP = {"how", "does", "do", "did", "what", "why", "who", "when", "where", "which", "is", "are", "was", "can",
        "could", "a", "an", "the", "to", "of", "in", "on", "for", "and", "or", "it", "its", "we", "us", "our",
        "you", "your", "they", "them", "things", "thing", "so", "much", "more", "work", "works", "make", "get", "need", "needs"}
SAME = {"computer": "machine", "computers": "machine", "ai": "machine", "robot": "machine", "robots": "machine",
        "machine": "machine", "machines": "machine", "price": "cost", "prices": "cost", "costs": "cost"}
RECENT_TOPICS = 30   # how many past topics a new one is compared with


def key_words(q: str) -> set:
    """The words that carry a question's meaning, with near-synonyms merged and plurals cut."""
    out = set()
    for w in re.sub(r"[^a-z0-9 ]", " ", q.lower()).split():
        if w in STOP:
            continue
        w = SAME.get(w, w)
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def too_close(q: str, past: List[str]) -> bool:
    """True when `q` asks much the same thing as a recent topic ("How does AI learn to work?" vs
    "How does a computer learn?"): one's key words (two or more) contain the other's, or half of them are shared."""
    a = key_words(q)
    for p in past:
        b = key_words(p)
        small, big = sorted((a, b), key=len)
        if not small:
            continue
        # a one-word question ("What is AI?") only clashes with the same one word
        if small == big or (len(small) >= 2 and (small <= big or len(a & b) / len(a | b) >= 0.5)):
            return True
    return False


def norm(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", q.lower()).replace("what is a ", "what is ").replace("what is an ", "what is ").strip()


class KidsTopicAgent:
    def __init__(self, llm=None):
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            from agents.llm import FreeLLM
            self._llm = FreeLLM()
        return self._llm

    # ── storage ──────────────────────────────────────────────────────────────
    def bank(self) -> List[Dict]:
        try:
            return json.loads((REPO / config.KIDS_TOPICS_FILE).read_text()).get("topics", [])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[kids-topics] bank unreadable: {e}")
            return []

    def history(self) -> List[Dict]:
        try:
            return json.loads((REPO / config.KIDS_HISTORY_FILE).read_text())
        except Exception:  # noqa: BLE001
            return []

    def mark_used(self, topics: List[Dict]) -> None:
        hist = self.history()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for t in topics:
            hist.append({"topic": t["topic"], "area": t.get("area", ""), "source": t.get("source", ""),
                         "world": t.get("world", ""), "opening": t.get("opening", ""),
                         "ending": t.get("ending", ""), "date": now})
        (REPO / config.KIDS_HISTORY_FILE).write_text(json.dumps(hist, indent=1, ensure_ascii=False))

    # ── sources ──────────────────────────────────────────────────────────────
    def headlines(self, limit: int = 30) -> List[str]:
        import feedparser

        feeds = [f.strip() for f in os.getenv("KIDS_FEEDS", "").split(",") if f.strip()] or list(DEFAULT_FEEDS)
        out: List[str] = []
        for url in feeds:
            try:
                for e in feedparser.parse(url).entries[:12]:
                    title = re.sub(r"\s+", " ", e.get("title", "")).strip()
                    if title and not BLOCK.search(title):
                        out.append(title)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[kids-topics] feed failed {url}: {str(e)[:80]}")
        logger.info(f"[kids-topics] {len(out)} headlines from {len(feeds)} feeds")
        return out[:limit]

    def ideas_from_headlines(self, heads: List[str], recent: Optional[List[str]] = None) -> List[Dict]:
        from agents.explainer_script_agent import parse_json_obj
        from templates import kids_prompts as P

        if not heads:
            return []
        prompt = P.CONCEPT_USER.format(headlines="\n".join(f"- {h}" for h in heads))
        if recent:
            prompt += ("\n\nAlready made (do NOT suggest these or anything close to them; pick a different idea):\n"
                       + "\n".join(f"- {t}" for t in recent))
        text = self.llm.complete(P.SYSTEM, prompt, max_tokens=1500, temperature=0.5)
        ideas = parse_json_obj(text).get("ideas") or []
        out = []
        for i in ideas:
            q = str(i.get("question", "")).strip()
            if 8 <= len(q) <= 60 and not BLOCK.search(q):
                out.append({"topic": q if q.endswith("?") else q + "?", "area": str(i.get("area", "")).lower(),
                            "source": "feed", "from_headline": str(i.get("why", ""))[:200]})
        return out

    # ── public ───────────────────────────────────────────────────────────────
    def next_area(self, hist: List[Dict]) -> str:
        cycle = [a.strip() for a in config.KIDS_AREA_CYCLE.split(",") if a.strip()] or ["tech", "finance"]
        return cycle[len(hist) % len(cycle)]

    def get_topics(self, count: int = 1, mode: Optional[str] = None) -> List[Dict]:
        mode = (mode or config.KIDS_TOPIC_MODE).lower()
        hist = self.history()
        used = {norm(h["topic"]) for h in hist}
        recent = [h["topic"] for h in hist[-RECENT_TOPICS:]]
        area = self.next_area(hist)
        picks: List[Dict] = []
        if mode in ("mixed", "feed"):
            try:
                ideas = [i for i in self.ideas_from_headlines(self.headlines(), recent)
                         if norm(i["topic"]) not in used and not too_close(i["topic"], recent)]
                ideas.sort(key=lambda i: i["area"] != area)  # preferred area first
                picks += ideas[:count]
            except Exception as e:  # noqa: BLE001 — the bank is always there
                logger.warning(f"[kids-topics] headline ideas failed: {str(e)[:150]}")
        if len(picks) < count and mode in ("mixed", "bank"):
            fresh = [b for b in self.bank() if norm(b["question"]) not in used
                     and not too_close(b["question"], recent)]
            fresh.sort(key=lambda b: b.get("area") != area)
            for b in fresh[: count - len(picks)]:
                picks.append({"topic": b["question"], "area": b.get("area", ""), "source": "bank",
                              "hint": b.get("hint", "")})
        for p in picks:
            logger.info(f"[kids-topics] → {p['topic']} ({p['area'] or '?'}, from {p['source']})")
        return picks[:count]
