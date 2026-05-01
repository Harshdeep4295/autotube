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
        publish_immediately: bool = True,
        gcs_path: Optional[str] = None,
    ) -> Dict:
        """
        Args:
            video_path: Path to the rendered MP4
            thumb_path: Path to the JPEG thumbnail
            script: Script dict (title, description, tags)
            slot_index: Which IST slot to schedule (ignored if publish_immediately=True)
            publish_immediately: If True, publish now. If False, schedule for slot_index time.
            gcs_path: If set, this is a retry from GCS backup (skip local file check)
        Returns:
            dict with video_id, url, publish_at, uploaded_at, or failure dict if upload fails
        """
        publish_at = None if publish_immediately else self._get_publish_time(slot_index)
        if publish_immediately:
            logger.info(f"Uploading: {script['title'][:60]} → publish immediately (NOW)")
        else:
            logger.info(f"Uploading: {script['title'][:60]} → schedule for {publish_at} UTC")

        try:
            video_id = self._upload_video(video_path, script, publish_at)
            self._set_thumbnail(video_id, thumb_path)

            # Upload SRT captions if generated alongside the video
            srt_path = str(Path(video_path).parent / "captions.srt")
            if Path(srt_path).exists():
                self._upload_captions(video_id, srt_path)

            self._save_to_log(script, video_id, publish_at)

            # Feature 1 hook: Format-specific tweaks (Shorts tagging, etc.)
            self._format_title_description(script, video_id)

            # Feature 3 hook: Post-upload operations (playlist insertion, etc.)
            self._post_upload(video_id, script)

            result = {
                "video_id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}",
                "publish_at": publish_at or datetime.utcnow().isoformat(),
                "uploaded_at": datetime.utcnow().isoformat(),
                "success": True,
            }
            logger.info(f"Uploaded successfully: {result['url']}")

            # If this was a GCS retry, clean up the backup
            if gcs_path:
                self._cleanup_gcs_backup(gcs_path)

            return result

        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            # Backup to GCS for later retry
            if not gcs_path:  # Don't double-backup if already from GCS
                self._backup_to_gcs(video_path, script)
            return {
                "success": False,
                "error": str(e),
                "title": script.get("title", ""),
                "video_path": video_path,
            }

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
                "privacyStatus": config.VIDEO_PRIVACY,
                "madeForKids": config.VIDEO_MADE_FOR_KIDS,
            },
        }
        # Only add publishAt if scheduling (not publishing immediately)
        if publish_at:
            body["status"]["publishAt"] = publish_at

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

    def _upload_captions(self, video_id: str, srt_path: str) -> None:
        """Upload SRT subtitle file to YouTube as an English caption track."""
        from googleapiclient.http import MediaFileUpload
        try:
            media = MediaFileUpload(srt_path, mimetype="text/plain", resumable=False)
            self.youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": "en",
                        "name": "English",
                        "isDraft": False,
                    }
                },
                media_body=media,
            ).execute()
            logger.info(f"Captions uploaded for video {video_id}")
        except Exception as e:
            logger.warning(f"Caption upload failed (video still published): {e}")

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
        token_data = None

        # Check if it's JSON content first (starts with "{")
        if token_path.startswith("{"):
            try:
                token_data = json.loads(token_path)
                logger.info("✓ Loaded YouTube token from JSON content (env var)")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse YouTube token JSON: {e}")
        # Otherwise try to load as file path
        else:
            try:
                if Path(token_path).exists():
                    with open(token_path) as f:
                        token_data = json.load(f)
                    logger.info(f"✓ Loaded YouTube token from file: {token_path}")
            except (FileNotFoundError, OSError, json.JSONDecodeError) as e:
                logger.debug(f"File load failed: {e}")

        if token_data is None:
            raise FileNotFoundError(
                f"YouTube token not found. "
                f"Set YOUTUBE_TOKEN_JSON in .env as JSON content or file path, "
                f"or run: python setup.py --auth"
            )

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", [
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.force-ssl",
            ]),
        )

        # Auto-refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token back to disk (only if it's a file path)
            if not token_path.startswith("{"):
                updated = json.loads(creds.to_json())
                updated.update({
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                })
                Path(token_path).parent.mkdir(parents=True, exist_ok=True)
                with open(token_path, "w") as f:
                    json.dump(updated, f, indent=2)
                logger.info("OAuth token refreshed and saved")
            else:
                logger.info("OAuth token refreshed (env var — not saving to disk)")

        return build("youtube", "v3", credentials=creds)

    # ── GCS Backup ────────────────────────────────────────────────────────────

    def _backup_to_gcs(self, video_path: str, script: Dict) -> None:
        """Backup failed video to GCS for later retry."""
        try:
            from agents.gcs_backup_agent import GCSBackupAgent
            backup = GCSBackupAgent()
            backup.upload_to_gcs(
                video_path,
                metadata={
                    "title": script.get("title", ""),
                    "description": script.get("description", ""),
                    "tags": script.get("tags", []),
                },
                attempt=1,
            )
        except Exception as e:
            logger.warning(f"Could not backup to GCS: {e}")

    def _cleanup_gcs_backup(self, gcs_path: str) -> None:
        """Delete backup from GCS after successful upload."""
        try:
            from agents.gcs_backup_agent import GCSBackupAgent
            backup = GCSBackupAgent()
            backup.delete_from_gcs(gcs_path)
        except Exception as e:
            logger.warning(f"Could not cleanup GCS backup: {e}")

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

    # ── Feature hooks (overridable by feature branches) ──────────────────────────

    def _format_title_description(self, script: Dict, video_id: str) -> None:
        """
        Feature 1 hook: Called after upload to apply format-specific tweaks.
        Default: no-op. Feature 1 (Shorts) overrides this.
        """
        pass

    def _post_upload(self, video_id: str, script: Dict) -> None:
        """
        Feature 3 hook: Called after upload for post-processing (playlist insertion).
        Default: no-op. Feature 3 (Auto-Playlist) overrides this.
        """
        pass
