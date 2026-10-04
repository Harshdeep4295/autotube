"""
Upload Agent
Authenticates with YouTube via OAuth2, uploads the video as a resumable upload, sets the
custom thumbnail and captions, and optionally schedules it (publishAt) and adds it to a playlist.
"""

import json
import logging
import os
import time
from datetime import datetime
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
        thumb_path: Optional[str],
        script: Dict,
        publish_at: Optional[str] = None,
        playlist: str = "",
    ) -> Dict:
        """
        Args:
            video_path: Path to the rendered MP4
            thumb_path: Path to the JPEG thumbnail (None = keep YouTube's own, e.g. for a Short)
            script: Script dict (title, description, tags)
            publish_at: ISO 8601 UTC time. The video stays private and YouTube publishes it then.
                        None = upload with config.VIDEO_PRIVACY and leave it.
            playlist: Playlist title to add the video to (created on the channel if missing). "" = none.
        Returns:
            dict with video_id, url, publish_at, uploaded_at, or a failure dict if the upload fails
        """
        if publish_at:
            logger.info(f"Uploading: {script['title'][:60]} → schedule for {publish_at} UTC")
        else:
            logger.info(f"Uploading: {script['title'][:60]} → {config.VIDEO_PRIVACY}")

        try:
            video_id = self._upload_video(video_path, script, publish_at)
            if thumb_path:
                self._set_thumbnail(video_id, thumb_path)

            # Upload SRT captions if generated alongside the video
            srt_path = str(Path(video_path).parent / "captions.srt")
            if Path(srt_path).exists():
                self._upload_captions(video_id, srt_path)

            self._save_to_log(script, video_id, publish_at)
            self._post_upload(video_id, playlist)

            result = {
                "video_id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}",
                "publish_at": publish_at or datetime.utcnow().isoformat(),
                "uploaded_at": datetime.utcnow().isoformat(),
                "success": True,
            }
            logger.info(f"Uploaded successfully: {result['url']}")
            return result

        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "title": script.get("title", ""),
                "video_path": video_path,
            }

    # ── Upload ────────────────────────────────────────────────────────────────

    def _upload_video(self, video_path: str, script: Dict, publish_at: str) -> str:
        from googleapiclient.http import MediaFileUpload

        title = script.get("title", "AutoTube Video")
        description = script.get("description", "")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": script.get("tags", []),
                "categoryId": config.VIDEO_CATEGORY_ID,
            },
            "status": {
                "privacyStatus": config.VIDEO_PRIVACY,
                # The writable field is selfDeclaredMadeForKids ("madeForKids" is read-only and was
                # silently ignored, which left uploads marked "made for kids"). Default: all ages,
                # not made for kids (channel audience = adults interested in local AI).
                "selfDeclaredMadeForKids": config.VIDEO_MADE_FOR_KIDS,
                # YouTube "altered or synthetic content" disclosure (AI voice / AI visuals).
                "containsSyntheticMedia": config.VIDEO_SYNTHETIC_MEDIA,
            },
        }
        # A scheduled publishAt requires the video to be private until then.
        if publish_at:
            body["status"]["privacyStatus"] = "private"
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
                f"or run: python generate_youtube_token.py"
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

    # ── Playlist ──────────────────────────────────────────────────────────────

    def _post_upload(self, video_id: str, playlist: str) -> None:
        """Add the video to the playlist with this exact title, creating it on first use."""
        if not playlist or not config.PLAYLIST_ENABLED:
            return
        try:
            playlist_id = self._find_playlist(playlist) or self._create_playlist(playlist)
            if playlist_id:
                self._add_to_playlist(video_id, playlist_id)
        except Exception as e:
            logger.warning(f"Playlist insertion failed (video still uploaded): {e}")

    def _find_playlist(self, title: str) -> Optional[str]:
        res = self.youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for item in res.get("items", []):
            if item["snippet"]["title"].strip().lower() == title.strip().lower():
                return item["id"]
        return None

    def _create_playlist(self, title: str) -> Optional[str]:
        res = self.youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": f"{title} — from {config.CHANNEL_NAME}"},
                "status": {"privacyStatus": "public"},
            },
        ).execute()
        logger.info(f"Created playlist '{title}': {res.get('id')}")
        return res.get("id")

    def _add_to_playlist(self, video_id: str, playlist_id: str, attempts: int = 4) -> None:
        """YouTube often answers 409 SERVICE_UNAVAILABLE for a few seconds after a playlist is
        created or a video is uploaded (first kids upload, 2026-10-02), so retry with a pause."""
        for attempt in range(attempts):
            try:
                self.youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": video_id},
                        }
                    },
                ).execute()
                logger.info(f"Video {video_id} added to playlist {playlist_id}")
                return
            except Exception as e:  # noqa: BLE001
                if attempt == attempts - 1:
                    raise
                logger.info(f"Playlist insert attempt {attempt + 1} failed ({str(e)[:80]}) — retrying")
                time.sleep(5 * (attempt + 1))
