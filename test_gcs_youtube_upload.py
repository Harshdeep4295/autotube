"""
Test script: Download video from GCS backup and upload to YouTube.
Validates both GCS connectivity and YouTube token auth.
"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

from config import config

# ── Step 1: Check GCS credentials ────────────────────────────────────────────

def check_gcs_access():
    """Verify GCS credentials are available."""
    sa_json = os.getenv("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        logger.error("❌ AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON not set in .env")
        return False
    try:
        sa_dict = json.loads(sa_json)
        logger.info(f"✓ GCP service account loaded (project: {sa_dict.get('project_id')})")
        return True
    except json.JSONDecodeError:
        logger.error("❌ AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON is not valid JSON")
        return False

# ── Step 2: List GCS bucket ──────────────────────────────────────────────────

def list_gcs_videos():
    """List all videos in GCS bucket."""
    try:
        from google.cloud import storage
        import json as json_module

        sa_json = os.getenv("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON", "")
        sa_dict = json_module.loads(sa_json)
        client = storage.Client.from_service_account_info(sa_dict)

        bucket_name = config.GCP_GCS_BUCKET
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix="videos/"))

        if not blobs:
            logger.warning(f"⚠️  No videos found in GCS bucket: {bucket_name}")
            return []

        logger.info(f"✓ Found {len(blobs)} objects in GCS:")
        videos = []
        for blob in blobs:
            size_mb = blob.size / (1024 * 1024)
            logger.info(f"  - {blob.name} ({size_mb:.1f} MB)")
            if blob.name.endswith('.mp4'):
                videos.append(blob.name)

        return videos
    except Exception as e:
        logger.error(f"❌ Could not list GCS bucket: {e}")
        return []

# ── Step 3: Download video from GCS ──────────────────────────────────────────

def download_video_from_gcs(gcs_path: str) -> str:
    """Download video from GCS to local temp file."""
    try:
        from google.cloud import storage
        import json as json_module

        sa_json = os.getenv("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON", "")
        sa_dict = json_module.loads(sa_json)
        client = storage.Client.from_service_account_info(sa_dict)

        bucket = client.bucket(config.GCP_GCS_BUCKET)
        blob = bucket.blob(gcs_path)

        local_path = Path("outputs") / Path(gcs_path).name
        local_path.parent.mkdir(parents=True, exist_ok=True)

        blob.download_to_filename(str(local_path))
        logger.info(f"✓ Downloaded: {local_path}")

        return str(local_path)
    except Exception as e:
        logger.error(f"❌ Could not download from GCS: {e}")
        return None

# ── Step 4: Test YouTube upload ──────────────────────────────────────────────

def test_youtube_upload(video_path: str, title: str = "GCS Backup Test Upload"):
    """Attempt to upload video to YouTube using fixed token."""
    try:
        from agents.upload_agent import UploadAgent

        # Create a dummy script object
        script = {
            "title": title,
            "description": f"Test upload from GCS backup at {datetime.utcnow().isoformat()}",
            "tags": ["test", "autotube"],
        }

        # Create a dummy thumbnail (just use a blank image)
        thumb_path = Path("outputs") / "test_thumb.jpg"
        thumb_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a minimal JPEG (1x1 pixel)
        if not thumb_path.exists():
            from PIL import Image
            img = Image.new('RGB', (1, 1), color='red')
            img.save(str(thumb_path))

        logger.info(f"Attempting YouTube upload: {title}")
        agent = UploadAgent()
        result = agent.publish(
            video_path=video_path,
            thumb_path=str(thumb_path),
            script=script,
            publish_immediately=True,
        )

        if result.get("success"):
            logger.info(f"✅ YouTube upload SUCCESSFUL!")
            logger.info(f"   Video ID: {result.get('video_id')}")
            logger.info(f"   URL: {result.get('url')}")
            logger.info(f"   Uploaded at: {result.get('uploaded_at')}")
            return True
        else:
            logger.error(f"❌ YouTube upload FAILED: {result.get('error')}")
            return False
    except Exception as e:
        logger.error(f"❌ Could not test upload: {e}")
        import traceback
        traceback.print_exc()
        return False

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 70)
    logger.info("Testing GCS Backup & YouTube Upload")
    logger.info("=" * 70)

    # Step 1: Check credentials
    logger.info("\n[Step 1] Checking GCS credentials...")
    if not check_gcs_access():
        logger.error("Cannot proceed without GCS credentials")
        sys.exit(1)

    # Step 2: List GCS bucket
    logger.info("\n[Step 2] Listing GCS bucket...")
    videos = list_gcs_videos()
    if not videos:
        logger.warning("No videos in GCS. This might be expected if the last pipeline succeeded.")
        logger.info("\nNote: If you had a failed upload, videos should appear in GCS.")
        logger.info("Try running: python orchestrator.py --dry-run --topic 'Test Topic'")
        sys.exit(0)

    # Step 3: Download first video
    logger.info(f"\n[Step 3] Downloading first video from GCS...")
    first_video_gcs_path = videos[0]
    video_path = download_video_from_gcs(first_video_gcs_path)
    if not video_path or not Path(video_path).exists():
        logger.error("Could not download video")
        sys.exit(1)

    # Step 4: Test YouTube upload
    logger.info(f"\n[Step 4] Testing YouTube upload...")
    success = test_youtube_upload(video_path)

    logger.info("\n" + "=" * 70)
    if success:
        logger.info("✅ All tests PASSED! Auth is working correctly.")
    else:
        logger.info("❌ Upload test FAILED. Check logs above for details.")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
