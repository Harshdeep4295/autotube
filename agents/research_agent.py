"""
Research Agent
Fetches trending topics from Google Trends, Reddit, and tech RSS feeds.
Scores and deduplicates topics, returns the top N ready for scripting.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import feedparser
import requests

from config import config

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch",
    "https://www.wired.com/feed/rss",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
]


class ResearchAgent:
    """Discovers trending topics from multiple sources with composite scoring."""

    def get_topics(self, count: int = config.TOPICS_PER_RUN) -> List[Dict]:
        """
        Returns up to `count` scored, deduplicated topic dicts.
        Each dict: {topic, angle, source, composite_score, reddit_mentions}
        Falls back gracefully if individual sources fail.
        """
        history = self._load_history()
        raw_topics: List[Dict] = []

        # Source 1: Google Trends
        try:
            raw_topics.extend(self._fetch_google_trends())
            logger.info(f"Google Trends: fetched {len(raw_topics)} topics")
        except Exception as e:
            logger.warning(f"Google Trends failed (skipping): {e}")

        # Source 2: Reddit
        try:
            reddit_topics = self._fetch_reddit()
            raw_topics.extend(reddit_topics)
            logger.info(f"Reddit: fetched {len(reddit_topics)} topics")
        except Exception as e:
            logger.warning(f"Reddit failed (skipping): {e}")

        # Source 3: RSS feeds
        try:
            rss_topics = self._fetch_rss()
            raw_topics.extend(rss_topics)
            logger.info(f"RSS: fetched {len(rss_topics)} topics")
        except Exception as e:
            logger.warning(f"RSS failed (skipping): {e}")

        if not raw_topics:
            logger.error("All research sources failed — no topics found")
            return []

        # Score and deduplicate
        scored = self._score_topics(raw_topics)
        filtered = self._deduplicate(scored, history)
        selected = filtered[:count]

        # Persist selected topics to history
        self._save_to_history(selected, history)

        logger.info(f"Selected {len(selected)} topics after scoring and deduplication")
        return selected

    # ── Source fetchers ───────────────────────────────────────────────────────

    def _fetch_google_trends(self) -> List[Dict]:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=330, timeout=(10, 25))
        trending = pytrends.trending_searches(pn=config.TRENDS_GEO.lower())
        topics = []
        for _, row in trending.iterrows():
            term = str(row[0]).strip()
            if len(term) > 5:
                topics.append({
                    "topic": term,
                    "angle": f"Why {term} is trending right now",
                    "source": "google_trends",
                    "trend_score": 70,
                    "reddit_mentions": 0,
                })
        return topics[:20]

    def _fetch_reddit(self) -> List[Dict]:
        topics = []
        headers = {"User-Agent": "AutoTube/1.0 (research bot)"}
        for sub in config.SUBREDDITS[:4]:  # limit to 4 subreddits per run
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code != 200:
                    continue
                posts = r.json().get("data", {}).get("children", [])
                for post in posts:
                    d = post.get("data", {})
                    title = d.get("title", "").strip()
                    score = d.get("score", 0)
                    if len(title) > 10 and score > 100:
                        topics.append({
                            "topic": title[:100],
                            "angle": f"What Reddit is saying about: {title[:60]}",
                            "source": f"reddit_r/{sub}",
                            "trend_score": min(score / 100, 50),
                            "reddit_mentions": score,
                        })
            except Exception as e:
                logger.debug(f"Reddit r/{sub} failed: {e}")
        return topics

    def _fetch_rss(self) -> List[Dict]:
        topics = []
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "")[:200]
                    if len(title) > 10:
                        topics.append({
                            "topic": title,
                            "angle": summary or f"Breaking: {title}",
                            "source": "rss",
                            "trend_score": 30,
                            "reddit_mentions": 0,
                        })
            except Exception as e:
                logger.debug(f"RSS feed {feed_url} failed: {e}")
        return topics

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score_topics(self, topics: List[Dict]) -> List[Dict]:
        """
        Composite score:
          trend_score × 0.50
          + min(reddit_mentions / 10, 30) × 0.30
          + source_bonus × 0.20
        """
        # Count how many sources mention each topic
        topic_counts: Dict[str, int] = {}
        for t in topics:
            key = self._normalize(t["topic"])
            topic_counts[key] = topic_counts.get(key, 0) + 1

        scored = []
        seen_normalized = set()
        for t in topics:
            key = self._normalize(t["topic"])
            if key in seen_normalized:
                continue
            seen_normalized.add(key)

            trend = float(t.get("trend_score", 30))
            reddit = t.get("reddit_mentions", 0)
            source_count = topic_counts.get(key, 1)

            composite = (
                trend * 0.50
                + min(reddit / 10, 30) * 0.30
                + min(source_count * 5, 20) * 0.20
            )
            t["composite_score"] = round(composite, 2)
            scored.append(t)

        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        return scored

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _deduplicate(self, topics: List[Dict], history: List[Dict]) -> List[Dict]:
        cutoff = datetime.utcnow() - timedelta(days=config.TOPIC_HISTORY_DAYS)
        recent_topics = [
            self._normalize(h["topic"])
            for h in history
            if datetime.fromisoformat(h.get("timestamp", "2000-01-01")) > cutoff
        ]
        return [
            t for t in topics
            if self._normalize(t["topic"]) not in recent_topics
        ]

    # ── History persistence ───────────────────────────────────────────────────

    def _load_history(self) -> List[Dict]:
        try:
            with open(config.HISTORY_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_to_history(self, selected: List[Dict], existing: List[Dict]) -> None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        now = datetime.utcnow().isoformat()
        new_entries = [
            {"topic": t["topic"], "timestamp": now, "source": t.get("source", "")}
            for t in selected
        ]
        # Keep last 90 days only
        cutoff = datetime.utcnow() - timedelta(days=90)
        kept = [
            h for h in existing
            if datetime.fromisoformat(h.get("timestamp", "2000-01-01")) > cutoff
        ]
        updated = kept + new_entries
        with open(config.HISTORY_FILE, "w") as f:
            json.dump(updated, f, indent=2)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, strip punctuation, truncate to 40 chars for fuzzy matching."""
        clean = re.sub(r"[^\w\s]", "", text.lower()).strip()
        return clean[:40]
