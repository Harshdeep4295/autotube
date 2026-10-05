"""
Research Agent
Fetches trending topics from free sources (no paid APIs), keeps the ones that match the
channel niche (config.NICHE_KEYWORDS), scores them and drops recently used ones.

Sources (each is best-effort; a failing source is skipped):
  1. Reddit hot posts (no-auth JSON API; often blocked from cloud IPs)
  2. RSS feeds (TechCrunch, Wired, NYT Tech)
  3. Hacker News (Firebase API — no auth, no rate limits)
  4. Dev.to (public API — no auth)
  5. Lobste.rs (RSS — no auth)

Topic history lives in data/topics_history.json.

Deduplication:
  - Exact normalized match (lowercase + strip punctuation + 40 chars)
  - Fuzzy similarity via difflib.SequenceMatcher (>0.75 ratio = too similar)
"""

import html
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

RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch",
    "https://www.wired.com/feed/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
]

LOBSTERS_FEEDS = [
    "https://lobste.rs/t/ai.rss",
    "https://lobste.rs/t/programming.rss",
]

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
DEVTO_URL = "https://dev.to/api/articles"


class ResearchAgent:
    """Discovers trending topics from free sources with composite scoring."""

    def _extract_key_data(self, text: str) -> Optional[str]:
        """Extract numbers, stats, or key phrases from text for angle enrichment."""
        if not text:
            return None

        # Look for percentages
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if pct_match:
            return f"{pct_match.group(1)}% increase"

        # Look for money amounts
        money_match = re.search(r'\$(\d+[KMB]?)', text)
        if money_match:
            return f"${money_match.group(1)}"

        # Look for X times multiplier
        mult_match = re.search(r'(\d+(?:\.\d+)?)\s*x\s+(?:faster|growth|bigger)', text)
        if mult_match:
            return f"{mult_match.group(1)}x improvement"

        return None

    def _enrich_angle(self, topic: str, summary: str, source: str) -> str:
        """
        Generate a richer angle with specific context instead of generic templates.

        Examples:
        - Before: "Why X is trending"
        - After: "Python 3.13 released with 5% performance boost — biggest update in 3 years"
        """
        if not summary or len(summary) < 20:
            return f"New development in {topic}"

        summary = summary[:300]  # Use first 300 chars only

        # Extract key data point
        key_data = self._extract_key_data(summary)

        # Build enriched angle based on source and content
        if source == "rss":
            # For RSS: use summary + extracted data
            if key_data and len(summary) > 50:
                return f"{summary[:100].rstrip('.')}. Key: {key_data}"
            return summary[:150]

        elif source == "reddit":
            # For Reddit: emphasize community discussion
            engagement = ""
            if "discusses" in summary.lower() or "debate" in summary.lower():
                engagement = " Intense debate in community."
            return f"{topic} — community talking about this. {engagement}".strip()

        elif source == "hackernews":
            # For HN: emphasize technical significance
            if any(word in summary.lower() for word in ["performance", "optimization", "benchmark"]):
                return f"{topic} — significant performance implications for developers"
            elif any(word in summary.lower() for word in ["security", "vulnerability", "exploit"]):
                return f"{topic} — security concern gaining attention"
            return f"{topic} — technical community interested"

        elif source == "devto":
            # For Dev.to: emphasize developer-relevant angle
            if key_data:
                return f"{topic} — {key_data}. Developer tools impact"
            return f"{topic} — actively discussed by developers"

        else:
            # Default
            if key_data:
                return f"{topic} — {key_data}"
            return f"{topic} — trending topic with engagement"

    def _score_topic_quality(self, topic: Dict) -> float:
        """
        Score topic quality for high-RPM potential.
        Returns 0-1 float indicating likelihood of being good YouTube content.

        Factors:
        - Has specific numbers/data (0.3 points)
        - Has actionable angle (0.25 points)
        - Has controversy/debate (0.2 points)
        - Source credibility (0.15 points)
        - Trending strength (0.1 points)
        """
        score = 0.0
        angle = topic.get("angle", "").lower()
        summary = topic.get("summary", "").lower()
        combined = f"{angle} {summary}"

        # Factor 1: Numbers/specificity (30%)
        if re.search(r'\d+%|\$\d+|(\d+\.?\d*)\s*x', combined):
            score += 0.3
        elif re.search(r'\d+', combined):
            score += 0.15

        # Factor 2: Actionable insight (25%)
        action_words = ["how to", "why", "should", "avoid", "best", "tips", "guide", "new", "released", "launched"]
        if any(word in angle for word in action_words):
            score += 0.25

        # Factor 3: Controversy/debate (20%)
        debate_words = ["vs", "battle", "controversy", "debate", "conflict", "threat", "competing"]
        if any(word in combined for word in debate_words):
            score += 0.2

        # Factor 4: Source credibility (15%)
        source = topic.get("source", "")
        source_weight = {
            "rss": 0.15,           # Official news
            "devto": 0.12,         # Developer community
            "hackernews": 0.15,    # Tech enthusiasts
            "lobsters": 0.1,       # Niche tech
            "reddit": 0.08,        # General discussion
        }
        score += source_weight.get(source, 0.05)

        # Factor 5: Trending strength (10%)
        trend = topic.get("trend_score", 0) / 100
        score += min(trend, 0.1)

        return min(score, 1.0)

    def get_topics(self, count: int = config.TOPICS_PER_RUN, record: bool = True) -> List[Dict]:
        """
        Returns up to `count` scored, deduplicated topic dicts.
        Each dict: {topic, angle, source, url, composite_score, quality_score, reddit_mentions}
        `record=False` leaves history untouched; the caller records the topic with
        mark_used() after a successful upload. A failing source is skipped.
        """
        history = self._load_history()
        if config.EXPLAINER_TOPIC_MODE == "bank":
            banked = self._from_bank(count, history)
            if banked:
                if record:
                    self._save_to_history(banked, history)
                return banked
            logger.warning("Topic bank is used up (or missing) — falling back to the news feeds")
        raw_topics: List[Dict] = []

        # Source 1: Reddit
        try:
            rd = self._fetch_reddit()
            raw_topics.extend(rd)
            logger.info(f"Reddit: {len(rd)} topics")
        except Exception as e:
            logger.warning(f"Reddit failed (skipping): {e}")

        # Source 2: RSS feeds
        try:
            rss = self._fetch_rss()
            raw_topics.extend(rss)
            logger.info(f"RSS: {len(rss)} topics")
        except Exception as e:
            logger.warning(f"RSS failed (skipping): {e}")

        # Source 3: Hacker News
        try:
            hn = self._fetch_hackernews()
            raw_topics.extend(hn)
            logger.info(f"Hacker News: {len(hn)} topics")
        except Exception as e:
            logger.warning(f"Hacker News failed (skipping): {e}")

        # Source 4: Dev.to
        try:
            dt = self._fetch_devto()
            raw_topics.extend(dt)
            logger.info(f"Dev.to: {len(dt)} topics")
        except Exception as e:
            logger.warning(f"Dev.to failed (skipping): {e}")

        # Source 5: Lobste.rs
        try:
            lb = self._fetch_lobsters()
            raw_topics.extend(lb)
            logger.info(f"Lobste.rs: {len(lb)} topics")
        except Exception as e:
            logger.warning(f"Lobste.rs failed (skipping): {e}")

        if not raw_topics:
            logger.error("All research sources failed — no topics found")
            return []

        for t in raw_topics:
            t["topic"] = self._clean(t["topic"])
            if t.get("summary"):
                t["summary"] = self._clean(t["summary"])

        before = len(raw_topics)
        raw_topics = [t for t in raw_topics if self.matches_niche(t)]
        logger.info(f"Niche filter ({config.CHANNEL_SUBNICHE[:40]}…): {before} → {len(raw_topics)} topics")
        if not raw_topics:
            logger.error("No research topic matches the channel niche")
            return []

        # Enrich angles with context and data
        for topic in raw_topics:
            summary = topic.get("summary", topic.get("angle", ""))
            source = topic.get("source", "rss")
            topic["angle"] = self._enrich_angle(topic["topic"], summary, source)
            topic["quality_score"] = self._score_topic_quality(topic)

        scored = self._score_topics(raw_topics)
        filtered = self._deduplicate(scored, history)

        # Keep only topics with a quality score of 0.35 or more
        quality_filtered = [t for t in filtered if t.get("quality_score", 0) >= 0.35]
        if quality_filtered:
            logger.info(f"Quality filter: {len(filtered)} → {len(quality_filtered)} topics (threshold: 0.35)")
            filtered = quality_filtered
        else:
            logger.warning(f"Quality filter removed all topics — using top {min(count, len(filtered))} anyway")

        selected = filtered[:count]

        if record:
            self._save_to_history(selected, history)
        logger.info(f"Selected {len(selected)} topics after scoring and deduplication")
        for s in selected:
            logger.info(f"  ✓ {s['topic'][:50]:<50} (quality: {s.get('quality_score', 0):.2f}, composite: {s['composite_score']:.2f})")

        return selected

    # ── Topic bank (data/explainer_topics.json) ───────────────────────────────

    def _from_bank(self, count: int, history: List[Dict]) -> List[Dict]:
        """Next unused evergreen topics. Each is one open-source tool; its README is the source."""
        try:
            with open(config.EXPLAINER_TOPICS_FILE) as f:
                bank = json.load(f).get("topics", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Topic bank unreadable: {e}")
            return []
        used = {h.get("normalized_topic") or self._normalize(h["topic"]) for h in history}
        picks = []
        for b in bank:
            if self._normalize(b["topic"]) in used:
                continue
            repo = b.get("repo", "")
            picks.append({
                "topic": b["topic"], "source": "bank", "summary": b.get("summary", ""),
                "url": f"https://github.com/{repo}" if repo else b.get("url", ""),
                "source_url": f"https://raw.githubusercontent.com/{repo}/{b.get('branch', 'main')}/README.md" if repo else "",
            })
            if len(picks) == count:
                break
        for p in picks:
            logger.info(f"  ✓ {p['topic'][:70]} (from the topic bank)")
        return picks

    # ── Source 1: Reddit ──────────────────────────────────────────────────────

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
                            "url": d.get("url") or f"https://www.reddit.com{d.get('permalink', '')}",
                            "summary": (d.get("selftext") or "")[:600],
                            "angle": f"What Reddit is saying about: {title[:60]}",
                            "source": f"reddit_r/{sub}",
                            "trend_score": min(score / 100, 50),
                            "reddit_mentions": score,
                        })
            except Exception as e:
                logger.debug(f"Reddit r/{sub} failed: {e}")
        return topics

    # ── Source 2: RSS feeds ───────────────────────────────────────────────────

    def _fetch_rss(self) -> List[Dict]:
        topics = []
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "")[:300]
                    if len(title) > 10:
                        topics.append({
                            "topic": title,
                            "url": entry.get("link", ""),
                            "angle": summary or f"Breaking: {title}",
                            "summary": summary,  # Preserve for enrichment
                            "source": "rss",
                            "trend_score": 30,
                            "reddit_mentions": 0,
                        })
            except Exception as e:
                logger.debug(f"RSS feed {feed_url} failed: {e}")
        return topics

    # ── Source 3: Hacker News ─────────────────────────────────────────────────

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
                        "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                        "angle": f"Why the tech community is talking about: {title[:60]}",
                        "source": "hackernews",
                        "trend_score": min(score / 20, 60),
                        "reddit_mentions": 0,
                    })
            except Exception:
                continue

        return topics

    # ── Source 4: Dev.to ──────────────────────────────────────────────────────

    def _fetch_devto(self) -> List[Dict]:
        """Fetch trending Dev.to articles — no auth required."""
        articles = []
        for tag in ("ai", "llm", "machinelearning"):
            r = requests.get(DEVTO_URL, params={"top": 7, "per_page": 10, "tag": tag}, timeout=10)
            if r.ok:
                articles += r.json()

        topics = []
        for art in articles:
            title = art.get("title", "").strip()
            tags = art.get("tag_list", [])
            reactions = art.get("public_reactions_count", 0)
            description = art.get("description", "")[:200]
            if len(title) > 10:
                topics.append({
                    "topic": title[:100],
                    "url": art.get("url", ""),
                    "angle": f"Developer perspective on: {title[:60]}",
                    "summary": description or f"Trending: {title[:80]}",  # For enrichment
                    "source": "devto",
                    "trend_score": min(reactions / 5, 40),
                    "reddit_mentions": 0,
                })
        return topics[:15]

    # ── Source 5: Lobste.rs ───────────────────────────────────────────────────

    def _fetch_lobsters(self) -> List[Dict]:
        """Fetch Lobste.rs AI and programming RSS — no auth."""
        topics = []
        for feed_url in LOBSTERS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:8]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "")[:300]
                    if len(title) > 10:
                        topics.append({
                            "topic": title,
                            "url": entry.get("link", ""),
                            "angle": summary or f"Community discussion: {title[:60]}",
                            "summary": summary,  # Preserve for enrichment
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
        from datetime import timezone
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=config.TOPIC_HISTORY_DAYS)
        recent_normalized = []
        for h in history:
            raw = h.get("used_at") or h.get("timestamp", "2000-01-01")
            try:
                dt = datetime.fromisoformat(raw)
                # Make offset-naive timestamps UTC-aware for comparison
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt > cutoff:
                    recent_normalized.append(
                        h.get("normalized_topic") or self._normalize(h["topic"])
                    )
            except (ValueError, TypeError):
                pass

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

    # ── History (data/topics_history.json) ────────────────────────────────────

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

    def mark_used(self, topics: List[Dict]) -> None:
        """Record topics in history. Call only after a video was successfully produced,
        so a failed run doesn't burn the topic."""
        if topics:
            self._save_to_history(topics, self._load_history())

    @staticmethod
    def matches_niche(topic: Dict) -> bool:
        text = f"{topic.get('topic', '')} {topic.get('summary', '')}".lower()
        for kw in config.NICHE_KEYWORDS:
            if len(kw) <= 4:
                if re.search(rf"\b{re.escape(kw)}s?\b", text):
                    return True
            elif kw in text:
                return True
        return False

    @staticmethod
    def _clean(text: str) -> str:
        """Decode HTML entities (e.g. '&amp;') and drop tags from feed text."""
        text = html.unescape(html.unescape(text or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, strip punctuation, truncate to 40 chars for fuzzy matching."""
        clean = re.sub(r"[^\w\s]", "", text.lower()).strip()
        return clean[:40]
