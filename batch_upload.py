#!/usr/bin/env python3
"""
AutoTube Batch Upload — Render N videos NOW, upload with staggered YouTube publish times.

Videos render immediately, one after another. YouTube publishes them on a schedule.

Usage:
    python batch_upload.py --count 5 --publish-delay 5 --start-offset 5.5
        → 5 videos render NOW
        → First publishes in 5.5 hours
        → Second publishes in 10.5 hours
        → etc (5h apart)

    python batch_upload.py --count 10 --publish-delay 24 --start-offset 0
        → 10 videos render NOW
        → First publishes immediately
        → Second publishes in 24 hours

    python batch_upload.py --count 3 --publish-delay 12 --dry-run
        → Test mode (render only, no upload)
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from config import config
from orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("batch_upload")


class BatchUploader:
    def __init__(self, count: int = 5, publish_delay_hours: float = 5, start_offset_hours: float = 5.5, dry_run: bool = False):
        self.count = count
        self.publish_delay_hours = publish_delay_hours
        self.start_offset_hours = start_offset_hours  # First video publishes in X hours from now
        self.dry_run = dry_run

    def run(self) -> None:
        """Render all videos NOW and upload with staggered publish times."""
        logger.info(f"\n{'='*70}")
        logger.info("🎬 AutoTube Batch Upload")
        logger.info(f"{'='*70}")
        logger.info(f"Configuration:")
        logger.info(f"  Videos to create: {self.count}")
        logger.info(f"  First publish in: {self.start_offset_hours} hour(s)")
        logger.info(f"  Publish interval: every {self.publish_delay_hours} hour(s)")
        logger.info(f"  Mode: {'DRY RUN (no upload)' if self.dry_run else 'LIVE (will upload to YouTube)'}")
        logger.info(f"{'='*70}\n")

        # Show publish schedule
        logger.info("📅 YouTube Publish Schedule:")
        now = datetime.utcnow()
        for i in range(self.count):
            publish_time = now + timedelta(hours=self.start_offset_hours + (i * self.publish_delay_hours))
            logger.info(f"  Video {i+1}: {publish_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        try:
            # Create orchestrator
            orchestrator = Orchestrator(dry_run=self.dry_run)

            # Fetch and process each video
            results = []
            for video_num in range(1, self.count + 1):
                logger.info(f"\n{'─'*70}")
                logger.info(f"VIDEO {video_num}/{self.count} - RENDERING NOW")
                logger.info(f"{'─'*70}")

                # Fetch pending video from Supabase
                row = orchestrator._fetch_pending_video()
                if not row:
                    logger.warning(f"Queue empty at video {video_num} — stopping")
                    break

                # Calculate publish time for this video (UTC)
                publish_time = now + timedelta(hours=self.start_offset_hours + ((video_num - 1) * self.publish_delay_hours))

                # Store publish time in the script for upload agent to use
                # (upload_agent checks for script["publish_at"] and uses YouTube's publishAt feature)
                if "script_json" not in row:
                    row["script_json"] = {}
                row["script_json"]["publish_at"] = publish_time.isoformat() + "Z"  # YouTube expects ISO format with Z

                # Process this video (render + upload with scheduled publish time)
                result = orchestrator._process_queued(row, slot_index=video_num - 1)

                # Add publish time info to result
                result["scheduled_publish"] = publish_time.strftime('%Y-%m-%d %H:%M:%S UTC')

                results.append(result)

                if result.get("success"):
                    logger.info(f"✓ Video {video_num} uploaded")
                    logger.info(f"  Title: {result.get('title', 'Untitled')[:60]}")
                    logger.info(f"  YouTube URL: {result.get('url', 'N/A')}")
                    logger.info(f"  Will publish: {publish_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                else:
                    logger.error(f"✗ Video {video_num} failed: {result.get('error', 'unknown')[:60]}")

            # Final summary
            logger.info(f"\n{'='*70}")
            logger.info("✓ Batch Complete")
            logger.info(f"{'='*70}")
            success_count = sum(1 for r in results if r.get("success"))
            logger.info(f"Processed: {success_count}/{self.count} videos\n")

            for i, result in enumerate(results, 1):
                status = "✓" if result.get("success") else "✗"
                title = result.get("title", "Untitled")[:50]
                pub_time = result.get("scheduled_publish", "N/A")
                logger.info(f"{status} Video {i}: {title}")
                logger.info(f"   Publish: {pub_time}")

            logger.info(f"{'='*70}\n")

            if success_count == self.count:
                logger.info("🎉 All videos uploaded! YouTube will publish them on schedule.")
            else:
                logger.warning(f"⚠️  {self.count - success_count} video(s) failed")
                sys.exit(1)

        except Exception as e:
            logger.error(f"Batch upload failed: {e}", exc_info=True)
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render N videos NOW and upload to YouTube with staggered publish times"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of videos to create (default: 5)",
    )
    parser.add_argument(
        "--publish-delay",
        type=float,
        default=5,
        help="Hours between each video's publish time (default: 5). Can be decimal (e.g., 0.5 = 30 min)",
    )
    parser.add_argument(
        "--start-offset",
        type=float,
        default=5.5,
        help="Hours to wait before first video publishes (default: 5.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render videos but skip YouTube upload (test mode)",
    )

    args = parser.parse_args()

    # Validate
    if args.count < 1:
        parser.error("--count must be >= 1")
    if args.publish_delay < 0:
        parser.error("--publish-delay must be >= 0")
    if args.start_offset < 0:
        parser.error("--start-offset must be >= 0")

    # Run batch
    uploader = BatchUploader(
        count=args.count,
        publish_delay_hours=args.publish_delay,
        start_offset_hours=args.start_offset,
        dry_run=args.dry_run,
    )
    uploader.run()


if __name__ == "__main__":
    main()
