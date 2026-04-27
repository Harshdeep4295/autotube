#!/usr/bin/env python3
"""
AutoTube Local Scheduler — fetch scripts from Supabase, render videos, upload to YouTube.
Runs on a schedule (every X hours) with Ken Burns fallback.

Usage:
    python scheduler.py --count 1 --interval 6              # Render 1 video every 6 hours
    python scheduler.py --count 2 --interval 12 --dry-run   # Dry-run: 2 videos every 12 hours
    python scheduler.py --count 1 --interval 1              # Every hour (useful for testing)
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import config
from orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")


class LocalScheduler:
    def __init__(self, count: int = 1, interval_hours: float = 6, dry_run: bool = False):
        self.count = count
        self.interval_hours = interval_hours
        self.dry_run = dry_run
        self.scheduler = BackgroundScheduler()
        self.next_run_time = None

    def run_job(self) -> None:
        """Execute one render cycle: fetch scripts from DB, render, upload."""
        logger.info(f"\n{'='*70}")
        logger.info(f"[SCHEDULED JOB] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Rendering {self.count} video(s) from Supabase queue...")
        logger.info(f"Next run: ~{self.interval_hours} hour(s) from now")
        logger.info(f"{'='*70}\n")

        try:
            orchestrator = Orchestrator(dry_run=self.dry_run)
            results = orchestrator.run_render(count=self.count)

            # Log summary
            success_count = sum(1 for r in results if r.get("success"))
            logger.info(f"\n✓ Job complete: {success_count}/{self.count} videos uploaded")
            for result in results:
                if result.get("success"):
                    title = result.get("title", "Untitled")
                    url = result.get("url", result.get("video_path", "local"))
                    logger.info(f"  ✓ {title[:50]} → {url}")
                else:
                    logger.error(f"  ✗ {result.get('topic', 'unknown')} - {result.get('error', 'unknown')[:60]}")

        except Exception as e:
            logger.error(f"Job failed: {e}", exc_info=True)

    def start(self) -> None:
        """Start the background scheduler."""
        logger.info(f"\n{'='*70}")
        logger.info("🎬 AutoTube Local Scheduler Started")
        logger.info(f"{'='*70}")
        logger.info(f"Configuration:")
        logger.info(f"  Videos per run: {self.count}")
        logger.info(f"  Interval: every {self.interval_hours} hour(s)")
        logger.info(f"  Mode: {'DRY RUN (no upload)' if self.dry_run else 'LIVE (will upload to YouTube)'}")
        logger.info(f"  Supabase: {config.SUPABASE_URL[:40]}..." if config.SUPABASE_URL else "  Supabase: NOT CONFIGURED")
        logger.info(f"  YouTube token: {'✓ Ready' if Path(config.YOUTUBE_TOKEN_FILE).exists() else '✗ Missing'}")
        logger.info(f"{'='*70}\n")

        # Add the job
        self.scheduler.add_job(
            self.run_job,
            trigger=IntervalTrigger(hours=self.interval_hours),
            id="render_job",
            name="Render from Supabase",
        )

        # Start scheduler
        self.scheduler.start()
        logger.info(f"✓ Scheduler started. Press Ctrl+C to stop.\n")

        # Run first job immediately (optional — comment out to wait for first interval)
        logger.info("Running first job immediately...")
        self.run_job()

        # Keep running
        try:
            while True:
                pass  # Scheduler runs in background thread
        except KeyboardInterrupt:
            logger.info("\n✓ Scheduler stopped by user")
            self.scheduler.shutdown()
            sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AutoTube Local Scheduler — fetch scripts from Supabase, render & upload videos"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of videos to produce per run (default: 1)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=6,
        help="Hours between scheduled runs (default: 6). Can be decimal (e.g., 0.5 = 30 minutes)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full pipeline but skip YouTube upload (test mode)",
    )

    args = parser.parse_args()

    # Validate
    if args.count < 1:
        logger.error("--count must be >= 1")
        sys.exit(1)
    if args.interval < 0.25:
        logger.error("--interval must be >= 0.25 (15 minutes)")
        sys.exit(1)

    # Start scheduler
    scheduler = LocalScheduler(
        count=args.count,
        interval_hours=args.interval,
        dry_run=args.dry_run,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
