"""
Kids topic agent: today's finance/tech headlines → the evergreen idea behind them
("RBI cuts repo rate" → "What is interest?"), with a curated bank as fallback.

Modes (KIDS_TOPIC_MODE): mixed (default) = headline ideas first, bank fallback;
feed = headlines only; bank = bank only. Areas alternate finance ↔ tech day to day.
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
                         "world": t.get("world", ""), "date": now})
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

    def ideas_from_headlines(self, heads: List[str]) -> List[Dict]:
        from agents.explainer_script_agent import parse_json_obj
        from templates import kids_prompts as P

        if not heads:
            return []
        text = self.llm.complete(P.SYSTEM, P.CONCEPT_USER.format(headlines="\n".join(f"- {h}" for h in heads)),
                                 max_tokens=1500, temperature=0.5)
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
        last = next((h.get("area") for h in reversed(hist) if h.get("area") in ("finance", "tech")), "tech")
        return "finance" if last == "tech" else "tech"

    def get_topics(self, count: int = 1, mode: Optional[str] = None) -> List[Dict]:
        mode = (mode or config.KIDS_TOPIC_MODE).lower()
        hist = self.history()
        used = {norm(h["topic"]) for h in hist}
        area = self.next_area(hist)
        picks: List[Dict] = []
        if mode in ("mixed", "feed"):
            try:
                ideas = [i for i in self.ideas_from_headlines(self.headlines()) if norm(i["topic"]) not in used]
                ideas.sort(key=lambda i: i["area"] != area)  # preferred area first
                picks += ideas[:count]
            except Exception as e:  # noqa: BLE001 — the bank is always there
                logger.warning(f"[kids-topics] headline ideas failed: {str(e)[:150]}")
        if len(picks) < count and mode in ("mixed", "bank"):
            fresh = [b for b in self.bank() if norm(b["question"]) not in used]
            fresh.sort(key=lambda b: b.get("area") != area)
            for b in fresh[: count - len(picks)]:
                picks.append({"topic": b["question"], "area": b.get("area", ""), "source": "bank",
                              "hint": b.get("hint", "")})
        for p in picks:
            logger.info(f"[kids-topics] → {p['topic']} ({p['area'] or '?'}, from {p['source']})")
        return picks[:count]
