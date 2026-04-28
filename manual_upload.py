#!/usr/bin/env python3
"""
Manual Video Upload Script
Upload a video to YouTube with detailed logging.

Usage:
    python manual_upload.py /path/to/video.mp4 --title "Video Title" --description "Video desc" --tags "tag1,tag2"

Or with default metadata from script file:
    python manual_upload.py /path/to/video.mp4 --script /path/to/script.json
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from agents.upload_agent import UploadAgent
from config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("manual_upload")


def main():
    parser = argparse.ArgumentParser(description="Manually upload a video to YouTube")
    parser.add_argument("video_path", help="Path to the video MP4 file")
    parser.add_argument("--title", help="Video title")
    parser.add_argument("--description", help="Video description")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--script", help="Path to script.json (uses title/description/tags from here)")
    parser.add_argument("--thumbnail", help="Path to thumbnail JPEG")
    parser.add_argument("--dry-run", action="store_true", help="Test without uploading")

    args = parser.parse_args()

    video_path = Path(args.video_path)
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return 1

    # Load metadata from script.json if provided
    script = {}
    if args.script:
        script_path = Path(args.script)
        if script_path.exists():
            with open(script_path) as f:
                script = json.load(f)
            logger.info(f"Loaded script from: {script_path}")
        else:
            logger.warning(f"Script file not found: {script_path}")

    # Override with CLI args
    if args.title:
        script["title"] = args.title
    if args.description:
        script["description"] = args.description
    if args.tags:
        script["tags"] = [t.strip() for t in args.tags.split(",")]

    # Validate required fields
    if not script.get("title"):
        logger.error("Title is required (--title or from --script)")
        return 1

    script.setdefault("description", "")
    script.setdefault("tags", [])

    logger.info("=" * 70)
    logger.info("MANUAL VIDEO UPLOAD")
    logger.info("=" * 70)
    logger.info(f"Video:       {video_path}")
    logger.info(f"Title:       {script['title']}")
    logger.info(f"Description: {script['description'][:100]}..." if len(script['description']) > 100 else f"Description: {script['description']}")
    logger.info(f"Tags:        {', '.join(script['tags']) if script['tags'] else '(none)'}")

    # Find thumbnail
    thumbnail_path = args.thumbnail
    if not thumbnail_path:
        # Look for thumbnail in same directory as video
        thumb_candidate = video_path.parent / "thumbnail.jpg"
        if thumb_candidate.exists():
            thumbnail_path = str(thumb_candidate)
            logger.info(f"Found thumbnail: {thumbnail_path}")

    if not thumbnail_path:
        logger.warning("No thumbnail found (upload will proceed without custom thumbnail)")
    elif not Path(thumbnail_path).exists():
        logger.error(f"Thumbnail not found: {thumbnail_path}")
        return 1

    if args.dry_run:
        logger.info("DRY RUN: Skipping actual upload")
        logger.info("=" * 70)
        return 0

    # Upload
    logger.info("=" * 70)
    logger.info("Starting upload...")
    logger.info("=" * 70)

    try:
        uploader = UploadAgent()
        result = uploader.publish(
            str(video_path),
            str(thumbnail_path) if thumbnail_path else "",
            script,
            slot_index=0,
            publish_immediately=True,
        )

        if result.get("success"):
            logger.info("=" * 70)
            logger.info("✅ UPLOAD SUCCESSFUL")
            logger.info("=" * 70)
            logger.info(f"Video ID:  {result.get('video_id')}")
            logger.info(f"URL:       {result.get('url')}")
            logger.info(f"Uploaded:  {result.get('uploaded_at')}")
            logger.info("=" * 70)
            print(f"\n🎉 Video uploaded: {result.get('url')}\n")
            return 0
        else:
            logger.error("=" * 70)
            logger.error("❌ UPLOAD FAILED")
            logger.error("=" * 70)
            logger.error(f"Error: {result.get('error')}")
            logger.error("=" * 70)
            return 1

    except Exception as e:
        logger.error("=" * 70)
        logger.error("❌ UPLOAD ERROR")
        logger.error("=" * 70)
        logger.error(f"Exception: {e}")
        logger.error("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
