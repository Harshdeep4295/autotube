"""
Research Agent
Fetches trending topics from 6 free sources — no paid APIs required.

Sources:
  1. Google Trends (pytrends)
  2. Reddit hot posts (no-auth JSON API)
  3. RSS feeds (TechCrunch, Wired, Reuters, NYT Tech)
  4. Hacker News (Firebase API — no auth, no rate limits)
  5. Dev.to (public API — no auth)
  6. Lobste.rs (RSS — no auth)

Topic history:
  - Primary: Supabase PostgreSQL (atomic writes — no race condition across 4 daily runs)
  - Fallback: local data/topics_history.json (used if SUPABASE_URL not set)

Deduplication:
  - Exact normalized match (lowercase + strip punctuation + 40 chars)
  - Fuzzy similarity via difflib.SequenceMatcher (>0.75 ratio = too similar)
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Dict, Optional

import feedparser
import requests

from config import config

logger = logging.getLogger(__name__)

RSS_FEEDS_BY_NICHE = {
    "AI & Tech": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.wired.com/feed/rss",
        "https://feeds.reuters.com/reuters/technologyNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    ],
    "Finance": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    ],
    "Business": [
        "https://feeds.feedburner.com/entrepreneur/latest",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.inc.com/home/updates",
    ],
    "Health": [
        "https://rss.medicalnewstoday.com/",
        "https://www.healthline.com/rss/health-news",
        "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
        "https://feeds.reuters.com/reuters/healthNews",
    ],
    "History": [
        "https://feeds.feedburner.com/smithsonianmag/history-archaeology",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.historydiscovery.com/feed/",
        "https://feeds.reuters.com/reuters/oddlyEnoughNews",
    ],
    "English Learning": [
        "https://feeds.feedburner.com/TechCrunch",          # tech English topics
        "https://rss.nytimes.com/services/xml/rss/nyt/Education.xml",
        "https://www.bbc.co.uk/learningenglish/english/rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    ],
}

# Default fallback (AI & Tech)
RSS_FEEDS = RSS_FEEDS_BY_NICHE.get(config.CHANNEL_NICHE, RSS_FEEDS_BY_NICHE["AI & Tech"])

LOBSTERS_FEEDS = [
    "https://lobste.rs/t/ai.rss",
    "https://lobste.rs/t/programming.rss",
]

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
DEVTO_URL = "https://dev.to/api/articles"


class ResearchAgent:
    """Discovers trending topics from 6 free sources with composite scoring."""

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
            gt = self._fetch_google_trends()
            raw_topics.extend(gt)
            logger.info(f"Google Trends: {len(gt)} topics")
        except Exception as e:
            logger.warning(f"Google Trends failed (skipping): {e}")

        # Source 2: Reddit
        try:
            rd = self._fetch_reddit()
            raw_topics.extend(rd)
            logger.info(f"Reddit: {len(rd)} topics")
        except Exception as e:
            logger.warning(f"Reddit failed (skipping): {e}")

        # Source 3: RSS feeds
        try:
            rss = self._fetch_rss()
            raw_topics.extend(rss)
            logger.info(f"RSS: {len(rss)} topics")
        except Exception as e:
            logger.warning(f"RSS failed (skipping): {e}")

        # Source 4: Hacker News
        try:
            hn = self._fetch_hackernews()
            raw_topics.extend(hn)
            logger.info(f"Hacker News: {len(hn)} topics")
        except Exception as e:
            logger.warning(f"Hacker News failed (skipping): {e}")

        # Source 5: Dev.to
        try:
            dt = self._fetch_devto()
            raw_topics.extend(dt)
            logger.info(f"Dev.to: {len(dt)} topics")
        except Exception as e:
            logger.warning(f"Dev.to failed (skipping): {e}")

        # Source 6: Lobste.rs
        try:
            lb = self._fetch_lobsters()
            raw_topics.extend(lb)
            logger.info(f"Lobste.rs: {len(lb)} topics")
        except Exception as e:
            logger.warning(f"Lobste.rs failed (skipping): {e}")

        if not raw_topics:
            logger.error("All research sources failed — no topics found")
            return []

        scored = self._score_topics(raw_topics)
        filtered = self._deduplicate(scored, history)
        selected = filtered[:count]

        self._save_to_history(selected, history)
        logger.info(f"Selected {len(selected)} topics after scoring and deduplication")
        return selected

    # ── Source 1: Google Trends ───────────────────────────────────────────────

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

    # ── Source 2: Reddit ──────────────────────────────────────────────────────

    def _fetch_reddit(self) -> List[Dict]:
        topics = []
        headers = {"User-Agent": "AutoTube/1.0 (research bot)"}
        for sub in config.ACTIVE_SUBREDDITS[:4]:
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

    # ── Source 3: RSS feeds ───────────────────────────────────────────────────

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

    # ── Source 4: Hacker News ─────────────────────────────────────────────────

    def _fetch_hackernews(self) -> List[Dict]:
        """Fetch top HN stories — no auth, no rate limit."""
        r = requests.get(HN_TOP_URL, timeout=10)
        r.raise_for_status()
        story_ids = r.json()[:30]  # top 30 IDs

        topics = []
        for sid in story_ids:
            if len(topics) >= 15:
                break
            try:
                item = requests.get(HN_ITEM_URL.format(sid), timeout=8).json()
                title = item.get("title", "").strip()
                score = item.get("score", 0)
                if len(title) > 10 and score > 50:
                    topics.append({
                        "topic": title[:100],
                        "angle": f"Why the tech community is talking about: {title[:60]}",
                        "source": "hackernews",
                        "trend_score": min(score / 20, 60),
                        "reddit_mentions": 0,
                    })
            except Exception:
                continue

        return topics

    # ── Source 5: Dev.to ──────────────────────────────────────────────────────

    def _fetch_devto(self) -> List[Dict]:
        """Fetch trending Dev.to articles — no auth required."""
        params = {"top": 7, "per_page": 20}
        r = requests.get(DEVTO_URL, params=params, timeout=10)
        r.raise_for_status()
        articles = r.json()

        topics = []
        for art in articles:
            title = art.get("title", "").strip()
            tags = art.get("tag_list", [])
            reactions = art.get("public_reactions_count", 0)
            if len(title) > 10:
                topics.append({
                    "topic": title[:100],
                    "angle": f"Developer perspective on: {title[:60]}",
                    "source": "devto",
                    "trend_score": min(reactions / 5, 40),
                    "reddit_mentions": 0,
                })
        return topics[:15]

    # ── Source 6: Lobste.rs ───────────────────────────────────────────────────

    def _fetch_lobsters(self) -> List[Dict]:
        """Fetch Lobste.rs AI and programming RSS — no auth."""
        topics = []
        for feed_url in LOBSTERS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:8]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "")[:200]
                    if len(title) > 10:
                        topics.append({
                            "topic": title,
                            "angle": summary or f"Community discussion: {title[:60]}",
                            "source": "lobsters",
                            "trend_score": 35,
                            "reddit_mentions": 0,
                        })
            except Exception as e:
                logger.debug(f"Lobste.rs feed {feed_url} failed: {e}")
        return topics

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score_topics(self, topics: List[Dict]) -> List[Dict]:
        """
        Composite score:
          trend_score × 0.50
          + min(reddit_mentions / 10, 30) × 0.30
          + source_count_bonus × 0.20
        """
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
        """Filter out topics too similar to anything in recent history."""
        cutoff = datetime.utcnow() - timedelta(days=config.TOPIC_HISTORY_DAYS)
        recent_normalized = [
            h.get("normalized_topic") or self._normalize(h["topic"])
            for h in history
            if datetime.fromisoformat(
                h.get("used_at") or h.get("timestamp", "2000-01-01")
            ) > cutoff
        ]

        filtered = []
        for t in topics:
            norm = self._normalize(t["topic"])
            if not self._is_too_similar(norm, recent_normalized):
                filtered.append(t)

        return filtered

    def _is_too_similar(self, norm_new: str, existing_normalized: List[str]) -> bool:
        """Return True if norm_new is an exact match OR >0.75 fuzzy match to any existing topic."""
        for existing in existing_normalized:
            if norm_new == existing:
                return True
            ratio = SequenceMatcher(None, norm_new, existing).ratio()
            if ratio > 0.75:
                return True
        return False

    # ── History: Supabase (primary) ───────────────────────────────────────────

    def _load_history(self) -> List[Dict]:
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            try:
                return self._load_history_supabase()
            except Exception as e:
                logger.warning(f"Supabase load failed, falling back to JSON: {e}")
        return self._load_history_json()

    def _save_to_history(self, selected: List[Dict], existing: List[Dict]) -> None:
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            try:
                self._save_to_history_supabase(selected)
                return
            except Exception as e:
                logger.warning(f"Supabase save failed, falling back to JSON: {e}")
        self._save_to_history_json(selected, existing)

    def _load_history_supabase(self) -> List[Dict]:
        from supabase import create_client
        client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
        result = (
            client.table("topic_history")
            .select("topic,normalized_topic,used_at")
            .gte("used_at", cutoff)
            .execute()
        )
        return result.data

    def _save_to_history_supabase(self, selected: List[Dict]) -> None:
        from supabase import create_client
        client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        rows = [
            {
                "topic": t["topic"],
                "normalized_topic": self._normalize(t["topic"]),
                "source": t.get("source", ""),
                "used_at": datetime.utcnow().isoformat(),
            }
            for t in selected
        ]
        client.table("topic_history").insert(rows).execute()
        logger.info(f"Saved {len(rows)} topics to Supabase")

    # ── History: JSON fallback ────────────────────────────────────────────────

    def _load_history_json(self) -> List[Dict]:
        try:
            with open(config.HISTORY_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_to_history_json(self, selected: List[Dict], existing: List[Dict]) -> None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        now = datetime.utcnow().isoformat()
        new_entries = [
            {
                "topic": t["topic"],
                "normalized_topic": self._normalize(t["topic"]),
                "timestamp": now,
                "used_at": now,
                "source": t.get("source", ""),
            }
            for t in selected
        ]
        cutoff = datetime.utcnow() - timedelta(days=90)
        kept = [
            h for h in existing
            if datetime.fromisoformat(
                h.get("used_at") or h.get("timestamp", "2000-01-01")
            ) > cutoff
        ]
        with open(config.HISTORY_FILE, "w") as f:
            json.dump(kept + new_entries, f, indent=2)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, strip punctuation, truncate to 40 chars for fuzzy matching."""
        clean = re.sub(r"[^\w\s]", "", text.lower()).strip()
        return clean[:40]
