"""
Analytics Agent — Pulls YouTube video performance metrics.
Stores views, RPM, avg view duration per video in data/topic_performance.json.
Used by research_agent to boost/penalize topic categories.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

PERFORMANCE_FILE = "data/topic_performance.json"


class AnalyticsAgent:
    def __init__(self):
        self.performance_data = self._load_performance()

    def _load_performance(self) -> Dict:
        try:
            with open(PERFORMANCE_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"last_updated": None, "videos": [], "niche_averages": {}}

    def _save_performance(self):
        os.makedirs(os.path.dirname(PERFORMANCE_FILE), exist_ok=True)
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(self.performance_data, f, indent=2)

    def pull_metrics(self) -> bool:
        """Pull YouTube Analytics for videos uploaded in last 30 days.
        Requires yt-analytics.readonly scope on the OAuth token."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            token_path = os.getenv("YOUTUBE_TOKEN_JSON", "data/youtube_token.json")
            token_data = None

            if os.path.exists(token_path):
                with open(token_path) as f:
                    token_data = json.load(f)
            elif token_path.startswith("{"):
                token_data = json.loads(token_path)

            if not token_data:
                logger.warning("No YouTube token found — skipping analytics pull")
                return False

            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
            )

            analytics = build("youtubeAnalytics", "v2", credentials=creds)

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            response = analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,estimatedRevenue,averageViewDuration,subscribersGained",
                dimensions="video",
                sort="-views",
                maxResults=50,
            ).execute()

            posted = []
            try:
                with open("data/posted_videos.json") as f:
                    posted = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            posted_map = {v.get("video_id"): v for v in posted}

            videos = []
            for row in response.get("rows", []):
                video_id = row[0]
                views = row[1]
                revenue = row[2]
                avg_duration = row[3]
                subs = row[4]

                posted_info = posted_map.get(video_id, {})
                rpm = (revenue / views * 1000) if views > 0 else 0

                videos.append({
                    "video_id": video_id,
                    "title": posted_info.get("title", ""),
                    "views": views,
                    "rpm": round(rpm, 2),
                    "avg_view_duration_seconds": avg_duration,
                    "subscribers_gained": subs,
                    "uploaded_at": posted_info.get("uploaded_at", ""),
                    "pulled_at": datetime.now().isoformat(),
                })

            self.performance_data["videos"] = videos
            self.performance_data["last_updated"] = datetime.now().isoformat()
            self._compute_averages()
            self._save_performance()

            logger.info(f"Analytics pulled: {len(videos)} videos tracked")
            return True

        except Exception as e:
            logger.warning(f"Analytics pull failed (non-blocking): {e}")
            return False

    def _compute_averages(self):
        videos = self.performance_data.get("videos", [])
        if not videos:
            return

        total_rpm = sum(v.get("rpm", 0) for v in videos)
        total_views = sum(v.get("views", 0) for v in videos)
        total_retention = sum(v.get("avg_view_duration_seconds", 0) for v in videos)
        n = len(videos)

        self.performance_data["niche_averages"] = {
            "avg_rpm": round(total_rpm / n, 2) if n else 0,
            "avg_views": round(total_views / n, 0) if n else 0,
            "avg_retention_seconds": round(total_retention / n, 0) if n else 0,
        }

    def get_topic_boost(self, topic: str) -> float:
        """Return a multiplier (0.5-2.0) based on how similar topics performed.
        Uses keyword matching against past video titles."""
        videos = self.performance_data.get("videos", [])
        if not videos:
            return 1.0

        topic_lower = topic.lower()
        keywords = set(topic_lower.split())

        matches = []
        for v in videos:
            title_words = set(v.get("title", "").lower().split())
            overlap = keywords & title_words
            if len(overlap) >= 2:
                matches.append(v)

        if not matches:
            return 1.0

        avg_rpm = self.performance_data.get("niche_averages", {}).get("avg_rpm", 5.0)
        match_rpm = sum(m.get("rpm", 0) for m in matches) / len(matches)

        if avg_rpm <= 0:
            return 1.0

        ratio = match_rpm / avg_rpm
        return max(0.5, min(2.0, ratio))
