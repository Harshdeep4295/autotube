"""
Test script: Upload generated video to YouTube.
Uses the video from the last dry-run to test YouTube auth.
"""

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

from agents.upload_agent import UploadAgent

def main():
    logger.info("=" * 70)
    logger.info("Testing YouTube Upload")
    logger.info("=" * 70)

    # Find latest video output (format: YYYYMMDD_xxxxxxx)
    outputs_dir = Path("outputs")
    video_dirs = sorted(
        [d for d in outputs_dir.iterdir() if d.is_dir() and d.name[0].isdigit()],
        reverse=True
    )

    if not video_dirs:
        logger.error("❌ No video outputs found. Run dry-run first: python orchestrator.py --dry-run")
        sys.exit(1)

    latest_dir = video_dirs[0]
    video_path = latest_dir / "video.mp4"
    thumb_path = latest_dir / "thumbnail.jpg"
    report_path = Path("logs") / f"report_{latest_dir.name[:8]}.json"

    logger.info(f"\nLatest output: {latest_dir.name}")
    logger.info(f"  Video: {video_path}")
    logger.info(f"  Thumbnail: {thumb_path}")

    if not video_path.exists():
        logger.error(f"❌ Video not found: {video_path}")
        sys.exit(1)

    if not thumb_path.exists():
        logger.error(f"❌ Thumbnail not found: {thumb_path}")
        sys.exit(1)

    # Extract script metadata from report
    script = {
        "title": "7 Tech Shifts Happening in the Next 90 Days That Change",
        "description": "Exploring the major technological shifts coming in the next quarter. From AI advancements to infrastructure changes, see what's transforming the tech landscape.",
        "tags": ["technology", "AI", "tech trends", "innovation", "future tech"],
    }

    # Try to read actual metadata from report if it exists
    if report_path.exists():
        try:
            with open(report_path) as f:
                report = json.load(f)
                if report.get("videos") and len(report["videos"]) > 0:
                    video_info = report["videos"][0]
                    script["title"] = video_info.get("title", script["title"])
                    script["description"] = video_info.get("description", script["description"])
                    script["tags"] = video_info.get("tags", script["tags"])
                    logger.info(f"✓ Loaded metadata from report")
        except Exception as e:
            logger.warning(f"Could not read report: {e}, using defaults")

    logger.info(f"\nUploading to YouTube:")
    logger.info(f"  Title: {script['title'][:60]}...")
    logger.info(f"  Tags: {', '.join(script['tags'])}")

    # Attempt upload
    try:
        agent = UploadAgent()
        logger.info("\n[Step 1] Authenticating with YouTube...")
        logger.info("✓ YouTube service initialized")

        logger.info("[Step 2] Uploading video (resumable upload)...")
        result = agent.publish(
            video_path=str(video_path),
            thumb_path=str(thumb_path),
            script=script,
            publish_immediately=True,
        )

        logger.info("\n" + "=" * 70)
        if result.get("success"):
            logger.info("✅ UPLOAD SUCCESSFUL!")
            logger.info(f"   Video ID: {result.get('video_id')}")
            logger.info(f"   URL: {result.get('url')}")
            logger.info(f"   Published at: {result.get('uploaded_at')}")
            logger.info("=" * 70)
            return 0
        else:
            logger.error(f"❌ UPLOAD FAILED: {result.get('error')}")
            logger.info("\n[Checking GCS Backup Status]")

            # Check if it was backed up to GCS
            backup_manifest = Path("data/upload_status.json")
            if backup_manifest.exists():
                with open(backup_manifest) as f:
                    manifest = json.load(f)
                    pending = [v for v in manifest if v.get("status") == "pending_gcs"]
                    if pending:
                        logger.info(f"⚠️  Video backed up to GCS (pending upload)")
                        logger.info(f"   GCS path: {pending[0].get('gcs_path')}")
                        logger.info(f"   This video will be retried on next pipeline run")

            logger.info("=" * 70)
            return 1

    except Exception as e:
        logger.error(f"❌ Exception during upload: {e}")
        import traceback
        traceback.print_exc()
        logger.info("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
