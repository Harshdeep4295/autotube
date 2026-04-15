"""
Upload Agent
Authenticates with YouTube via OAuth2, uploads the video as a resumable upload,
sets the custom thumbnail, and schedules it at the correct IST publish slot.
Token is auto-refreshed and saved back on every run.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from config import config

logger = logging.getLogger(__name__)


class UploadAgent:
    """Uploads videos to YouTube using the Data API v3."""

    def __init__(self):
        self.youtube = self._build_service()

    def publish(
        self,
        video_path: str,
        thumb_path: str,
        script: Dict,
        slot_index: int = 0,
    ) -> Dict:
        """
        Args:
            video_path: Path to the rendered MP4
            thumb_path: Path to the JPEG thumbnail
            script: Script dict (title, description, tags)
            slot_index: Which IST slot to schedule (0=morning, 1=noon, 2=afternoon, 3=evening)
        Returns:
            dict with video_id, url, publish_at, uploaded_at
        """
        publish_at = self._get_publish_time(slot_index)
        logger.info(f"Uploading: {script['title'][:60]} → publish at {publish_at} UTC")

        video_id = self._upload_video(video_path, script, publish_at)
        self._set_thumbnail(video_id, thumb_path)
        self._save_to_log(script, video_id, publish_at)

        result = {
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
            "publish_at": publish_at,
            "uploaded_at": datetime.utcnow().isoformat(),
            "success": True,
        }
        logger.info(f"Uploaded successfully: {result['url']}")
        return result

    # ── Upload ────────────────────────────────────────────────────────────────

    def _upload_video(self, video_path: str, script: Dict, publish_at: str) -> str:
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": script.get("title", "AutoTube Video"),
                "description": script.get("description", ""),
                "tags": script.get("tags", []),
                "categoryId": config.VIDEO_CATEGORY_ID,
            },
            "status": {
                "privacyStatus": "private" if publish_at else config.VIDEO_PRIVACY,
                "publishAt": publish_at,
                "madeForKids": config.VIDEO_MADE_FOR_KIDS,
            },
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

        return response["id"]

    def _set_thumbnail(self, video_id: str, thumb_path: str) -> None:
        from googleapiclient.http import MediaFileUpload
        try:
            media = MediaFileUpload(thumb_path, mimetype="image/jpeg")
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()
            logger.info(f"Thumbnail set for video {video_id}")
        except Exception as e:
            logger.warning(f"Thumbnail upload failed (video still uploaded): {e}")

    # ── Scheduling ────────────────────────────────────────────────────────────

    def _get_publish_time(self, slot_index: int) -> str:
        """
        Returns an ISO 8601 UTC datetime string for the next occurrence
        of the given slot index (today if it hasn't passed, otherwise tomorrow).
        """
        utc_times = config.UPLOAD_TIMES_UTC
        slot = utc_times[slot_index % len(utc_times)]
        h, m = map(int, slot.split(":"))

        now_utc = datetime.now(timezone.utc)
        candidate = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)

        # If this slot already passed today, schedule for tomorrow
        if candidate <= now_utc:
            candidate += timedelta(days=1)

        return candidate.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _build_service(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_path = config.YOUTUBE_TOKEN_FILE
        if not Path(token_path).exists():
            raise FileNotFoundError(
                f"YouTube token not found at '{token_path}'. "
                f"Run: python setup.py --auth"
            )

        with open(token_path) as f:
            token_data = json.load(f)

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"]),
        )

        # Auto-refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token back to disk
            updated = json.loads(creds.to_json())
            updated.update({
                "token": creds.token,
                "refresh_token": creds.refresh_token,
            })
            with open(token_path, "w") as f:
                json.dump(updated, f, indent=2)
            logger.info("OAuth token refreshed and saved")

        return build("youtube", "v3", credentials=creds)

    # ── Log ───────────────────────────────────────────────────────────────────

    def _save_to_log(self, script: Dict, video_id: str, publish_at: str) -> None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        try:
            with open(config.POSTED_FILE) as f:
                log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log = []

        log.append({
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
            "title": script.get("title", ""),
            "publish_at": publish_at,
            "uploaded_at": datetime.utcnow().isoformat(),
        })

        with open(config.POSTED_FILE, "w") as f:
            json.dump(log, f, indent=2)
