"""
Comment Research Agent
Fetches YouTube comments from own and competitor videos, extracts audience questions,
and converts them into research topics with scoring.

Sources:
  - Own video comments (recent uploads)
  - Competitor video comments (top videos in CHANNEL_NICHE)

Processing:
  1. Extract audience questions via regex patterns
  2. Deduplicate and frequency-count
  3. Score by frequency + convert to topic dicts
"""

import logging
import re
from typing import List, Dict, Optional

from config import config

logger = logging.getLogger(__name__)


class CommentResearchAgent:
    """Extracts audience questions from YouTube comments."""

    def __init__(self, youtube_service):
        """
        Args:
            youtube_service: Authenticated YouTube Data API v3 service object
        """
        self.youtube = youtube_service

    def get_comment_topics(
        self,
        own_videos: int,
        competitor_videos: int,
        max_per_video: int,
    ) -> List[Dict]:
        """
        Extract audience questions from own and competitor video comments.

        Args:
            own_videos: Number of own recent videos to fetch comments from
            competitor_videos: Number of competitor videos to fetch comments from
            max_per_video: Max comments to fetch per video

        Returns:
            List of topic dicts: {topic, angle, source, trend_score, composite_score, quality_score}
        """
        all_comments = []

        # Own uploads
        try:
            own_ids = self._get_own_video_ids(own_videos)
            logger.info(f"Fetching comments from {len(own_ids)} own videos")
            for vid_id in own_ids:
                comments = self._fetch_comments(vid_id, max_per_video)
                all_comments.extend(comments)
                logger.debug(f"  Video {vid_id}: {len(comments)} comments")
        except Exception as e:
            logger.warning(f"Failed to fetch own video comments: {e}")

        # Competitor videos
        try:
            comp_ids = self._get_competitor_video_ids(competitor_videos)
            logger.info(f"Fetching comments from {len(comp_ids)} competitor videos")
            for vid_id in comp_ids:
                comments = self._fetch_comments(vid_id, max_per_video)
                all_comments.extend(comments)
                logger.debug(f"  Video {vid_id}: {len(comments)} comments")
        except Exception as e:
            logger.warning(f"Failed to fetch competitor video comments: {e}")

        if not all_comments:
            logger.info("No comments found in own or competitor videos")
            return []

        logger.info(f"Extracted {len(all_comments)} total comments")

        # Extract questions and score
        questions = self._extract_questions(all_comments)
        logger.info(f"Found {len(questions)} unique audience questions")

        topics = []
        for q in questions:
            freq = sum(1 for c in all_comments if q.lower() in c.lower())
            topic = self._score_comment_topic(q, freq)
            if topic:
                topics.append(topic)

        logger.info(f"Converted to {len(topics)} scored topics")
        return topics

    def _get_own_video_ids(self, max_videos: int) -> List[str]:
        """
        Fetch own video IDs from the authenticated user's uploads playlist.

        Uses YouTube API:
          channels().list(part='contentDetails', mine=True) → get uploadsPlaylistId
          playlistItems().list(playlistId=..., maxResults=max_videos) → video IDs

        Returns:
            List of video IDs (up to max_videos)
        """
        try:
            channel_res = self.youtube.channels().list(
                part="contentDetails",
                mine=True,
            ).execute()

            if not channel_res.get("items"):
                logger.warning("No authenticated channel found (YouTube auth may be missing)")
                return []

            uploads_playlist_id = channel_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

            items_res = self.youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=min(max_videos, 50),
            ).execute()

            video_ids = []
            for item in items_res.get("items", []):
                vid_id = item["snippet"]["resourceId"].get("videoId")
                if vid_id:
                    video_ids.append(vid_id)

            logger.info(f"_get_own_video_ids: found {len(video_ids)} own videos")
            return video_ids[:max_videos]

        except Exception as e:
            logger.warning(f"_get_own_video_ids failed: {e}")
            return []

    def _get_competitor_video_ids(self, max_videos: int) -> List[str]:
        """
        Fetch top videos in CHANNEL_NICHE by viewCount.

        Uses YouTube API search:
          search().list(q=CHANNEL_NICHE, type='video', order='viewCount', maxResults=max_videos)

        Note: Costs 100 quota units per call, but provides valuable competitor insights.

        Returns:
            List of video IDs (up to max_videos)
        """
        try:
            search_res = self.youtube.search().list(
                part="snippet",
                q=config.CHANNEL_NICHE,
                type="video",
                order="viewCount",
                regionCode="US",
                maxResults=min(max_videos, 50),
            ).execute()

            video_ids = []
            for item in search_res.get("items", []):
                vid_id = item["id"].get("videoId")
                if vid_id:
                    video_ids.append(vid_id)

            logger.info(f"_get_competitor_video_ids: found {len(video_ids)} competitor videos in '{config.CHANNEL_NICHE}'")
            return video_ids[:max_videos]

        except Exception as e:
            logger.warning(f"_get_competitor_video_ids failed: {e}")
            return []

    def _fetch_comments(self, video_id: str, max_results: int) -> List[str]:
        """
        Fetch top comments from a YouTube video.

        Uses YouTube API:
          commentThreads().list(videoId=video_id, order='relevance', maxResults=max_results)

        Extracts textDisplay from each top-level comment.

        Args:
            video_id: YouTube video ID
            max_results: Max comments to fetch (0-100)

        Returns:
            List of comment text strings
        """
        try:
            comments_res = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                order="relevance",
                textFormat="plainText",
                maxResults=min(max_results, 100),
            ).execute()

            comments = []
            for item in comments_res.get("items", []):
                comment_text = item["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "")
                if comment_text.strip():
                    comments.append(comment_text)

            return comments

        except Exception as e:
            logger.debug(f"_fetch_comments({video_id}) failed: {e}")
            return []

    def _extract_questions(self, comments: List[str]) -> List[str]:
        """
        Extract audience questions from comment text using regex patterns.

        Patterns:
          - "can you [make/do] X"
          - "video on X" / "videos about X"
          - "what about X"
          - "how [does/do] X"
          - "I wish you [covered/cover/had covered] X"
          - "next video [should be|on] X"

        Filters:
          - Keep only 3-10 word questions (meaningful length)
          - Remove duplicates
          - Top 20 unique questions

        Args:
            comments: List of comment text strings

        Returns:
            List of extracted questions (unique, sorted by frequency)
        """
        questions = set()

        for comment in comments:
            comment_lower = comment.lower()

            # Pattern 1: "can you make/do/create X"
            m = re.search(r"can you (?:make|do|create|build) (?:a|an)? ?([^?.\n]+)", comment_lower)
            if m:
                q = m.group(1).strip()
                if q:
                    questions.add(q)

            # Pattern 2: "video/videos on/about X"
            m = re.search(r"(?:video|videos|tutorial) (?:on|about) ([^?.\n]+)", comment_lower)
            if m:
                q = m.group(1).strip()
                if q:
                    questions.add(q)

            # Pattern 3: "what about X"
            m = re.search(r"what about ([^?.\n]+)", comment_lower)
            if m:
                q = m.group(1).strip()
                if q:
                    questions.add(q)

            # Pattern 4: "how does/do X"
            m = re.search(r"how (?:does|do) ([^?.\n]+)", comment_lower)
            if m:
                q = m.group(1).strip()
                if q:
                    questions.add(q)

            # Pattern 5: "I wish you covered/cover X"
            m = re.search(r"i wish you (?:covered|cover|had covered) ([^?.\n]+)", comment_lower)
            if m:
                q = m.group(1).strip()
                if q:
                    questions.add(q)

            # Pattern 6: "next video should be/on X"
            m = re.search(r"next video (?:should be|on) ([^?.\n]+)", comment_lower)
            if m:
                q = m.group(1).strip()
                if q:
                    questions.add(q)

        # Filter: keep only meaningful questions (3-10 words, reasonable length)
        filtered = []
        for q in questions:
            word_count = len(q.split())
            if 3 <= word_count <= 10 and len(q) < 150:
                filtered.append(q)

        # Return top 20 unique questions
        logger.debug(f"_extract_questions: {len(questions)} raw → {len(filtered)} filtered")
        return list(filtered)[:20]

    def _score_comment_topic(self, question: str, frequency: int) -> Optional[Dict]:
        """
        Convert an extracted question into a topic dict matching existing schema.

        Scoring:
          - trend_score: frequency * 10 (capped at 100)
          - composite_score: frequency * 5 (capped at 50) — will be recalculated by _score_topics()
          - quality_score: 0.5 — medium quality (audience questions are good but not validated)

        Args:
            question: Extracted audience question
            frequency: How many times this question appeared in comments

        Returns:
            Dict with schema: {topic, angle, source, trend_score, reddit_mentions, composite_score, quality_score}
            Or None if question is too short/invalid
        """
        if not question or len(question.strip()) < 3:
            return None

        # Clean up question to create topic title
        topic_text = question.capitalize()
        if not topic_text.endswith("?"):
            topic_text += "?"

        return {
            "topic": topic_text,
            "angle": f"Audience question from YouTube comments: {question}",
            "summary": f"Asked {frequency} times in comments",
            "source": "youtube_comments",
            "trend_score": min(frequency * 10, 100),  # Scale frequency to 0-100
            "reddit_mentions": 0,
            "composite_score": min(frequency * 5, 50),  # Will be recalculated by _score_topics()
            "quality_score": 0.5,  # Medium quality (will be recalculated by _score_topic_quality())
        }
