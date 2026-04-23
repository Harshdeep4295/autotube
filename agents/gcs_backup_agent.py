"""
GCS Backup Agent — Saves failed YouTube uploads to Google Cloud Storage for later retry.
Implements resilient video backup: if YouTube upload fails, video is saved to GCS,
and retried on next pipeline run.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)


class GCSBackupAgent:
    """Manages video backup and retry from Google Cloud Storage."""

    def __init__(self):
        self.gcs_client = self._init_gcs()
        self.bucket_name = config.GCP_GCS_BUCKET
        self.manifest_path = Path(config.DATA_DIR) / "upload_status.json"

    def upload_to_gcs(
        self,
        video_path: str,
        metadata: Dict,
        attempt: int = 1,
    ) -> Optional[str]:
        """
        Upload video to GCS as backup (for failed YouTube uploads).
        Returns: gcs_path (gs://bucket/videos/...) or None if failed.
        """
        try:
            if not self.gcs_client:
                logger.warning("GCS not configured — cannot backup video")
                return None

            video_name = Path(video_path).name
            gcs_path = f"videos/pending/{video_name}"

            bucket = self.gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(video_path)

            logger.info(f"Video backed up to GCS: gs://{self.bucket_name}/{gcs_path}")

            # Save metadata to manifest
            self._add_to_manifest(gcs_path, metadata, attempt)

            return gcs_path
        except Exception as e:
            logger.error(f"GCS backup failed: {e}")
            return None

    def get_pending_uploads(self) -> List[Dict]:
        """Get list of videos pending upload to YouTube from manifest."""
        if not self.manifest_path.exists():
            return []

        try:
            with open(self.manifest_path) as f:
                manifest = json.load(f)
            pending = [v for v in manifest if v.get("status") == "pending_gcs"]
            logger.info(f"Found {len(pending)} pending uploads in GCS")
            return pending
        except Exception as e:
            logger.warning(f"Could not read upload manifest: {e}")
            return []

    def delete_from_gcs(self, gcs_path: str) -> bool:
        """Delete video from GCS after successful YouTube upload."""
        try:
            if not self.gcs_client:
                return False

            bucket = self.gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(gcs_path)
            blob.delete()

            logger.info(f"Deleted from GCS: gs://{self.bucket_name}/{gcs_path}")
            self._remove_from_manifest(gcs_path)
            return True
        except Exception as e:
            logger.warning(f"Could not delete from GCS: {e}")
            return False

    def _add_to_manifest(self, gcs_path: str, metadata: Dict, attempt: int) -> None:
        """Add video to upload manifest for retry tracking."""
        os.makedirs(config.DATA_DIR, exist_ok=True)

        try:
            with open(self.manifest_path) as f:
                manifest = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            manifest = []

        entry = {
            "gcs_path": gcs_path,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "status": "pending_gcs",
            "attempts": attempt,
            "first_backed_up": datetime.utcnow().isoformat(),
            "last_retry": datetime.utcnow().isoformat(),
        }

        # Check if already in manifest (prevent duplicates)
        if not any(v.get("gcs_path") == gcs_path for v in manifest):
            manifest.append(entry)
            with open(self.manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Added to manifest: {metadata.get('title', gcs_path)[:60]}")

    def _remove_from_manifest(self, gcs_path: str) -> None:
        """Remove video from manifest after successful upload."""
        if not self.manifest_path.exists():
            return

        try:
            with open(self.manifest_path) as f:
                manifest = json.load(f)

            # Mark as uploaded instead of removing (for audit trail)
            for entry in manifest:
                if entry.get("gcs_path") == gcs_path:
                    entry["status"] = "uploaded"
                    entry["uploaded_at"] = datetime.utcnow().isoformat()

            with open(self.manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not update manifest: {e}")

    def _init_gcs(self):
        """Initialize GCS client from service account JSON."""
        try:
            from google.cloud import storage
            sa_json = os.getenv("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON", "")
            if not sa_json:
                logger.warning("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON not set — GCS backup disabled")
                return None

            import json as json_module
            sa_dict = json_module.loads(sa_json)
            return storage.Client.from_service_account_info(sa_dict)
        except Exception as e:
            logger.warning(f"Could not initialize GCS client: {e}")
            return None
