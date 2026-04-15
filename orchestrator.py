"""
AutoTube Orchestrator — main pipeline entry point.

Usage:
    python orchestrator.py                        # 1 video, auto research, live upload
    python orchestrator.py --dry-run              # full pipeline, skip upload
    python orchestrator.py --count 3              # produce 3 videos
    python orchestrator.py --topic "AI news"      # override topic research
    python orchestrator.py --dry-run --count 1    # safe test run (no upload)
"""

import argparse
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from config import config
from agents.research_agent import ResearchAgent
from agents.script_agent import ScriptAgent
from agents.voice_agent import VoiceAgent
from agents.video_agent import VideoAgent
from agents.thumbnail_agent import ThumbnailAgent
from agents.upload_agent import UploadAgent


def setup_logging(run_id: str) -> logging.Logger:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_path = f"{config.LOG_DIR}/pipeline_{datetime.now().strftime('%Y%m%d')}_{run_id}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path),
        ],
    )
    return logging.getLogger("orchestrator")


class Orchestrator:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.run_id = uuid.uuid4().hex[:8]
        self.logger = setup_logging(self.run_id)
        self.logger.info(f"=== AutoTube Pipeline ===")
        self.logger.info(f"Run ID     : {self.run_id}")
        self.logger.info(f"Provider   : {config.SCRIPT_MODEL_PROVIDER}")
        self.logger.info(f"Mode       : {'DRY RUN (no upload)' if dry_run else 'LIVE'}")
        self.logger.info(f"Niche      : {config.CHANNEL_NICHE}")

        self.research   = ResearchAgent()
        self.scripter   = ScriptAgent()
        self.voice      = VoiceAgent()
        self.video      = VideoAgent()
        self.thumbnail  = ThumbnailAgent()
        self.uploader   = None if dry_run else UploadAgent()

    def run(self, count: int = 1, topic_override: Optional[str] = None) -> List[Dict]:
        """Run the full pipeline for `count` videos. Returns list of result dicts."""

        # Step 1: Research topics
        if topic_override:
            topics = [{
                "topic": topic_override,
                "angle": f"Why {topic_override} matters right now",
                "source": "manual_override",
                "composite_score": 99,
                "reddit_mentions": 0,
            }]
        else:
            self.logger.info("Step 1/6: Researching trending topics…")
            topics = self.research.get_topics(count)

        if not topics:
            self.logger.error("No topics found — aborting pipeline")
            return []

        self.logger.info(f"Topics: {[t['topic'][:50] for t in topics[:count]]}")

        results = []
        for i, topic in enumerate(topics[:count]):
            self.logger.info(f"\n{'─'*60}")
            self.logger.info(f"Video {i+1}/{count}: {topic['topic'][:60]}")
            result = self._process_one(topic, slot_index=i)
            results.append(result)
            if result.get("success"):
                self.logger.info(f"  ✓ Done: {result.get('url', result.get('video_path', ''))}")
            else:
                self.logger.error(f"  ✗ Failed: {result.get('error', 'unknown')[:80]}")

        self._print_summary(results)
        self._save_report(results)
        return results

    def _process_one(self, topic: Dict, slot_index: int = 0) -> Dict:
        job_id = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        out_dir = Path(config.OUTPUT_DIR) / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "job_id":   job_id,
            "topic":    topic["topic"],
            "success":  False,
            "started":  datetime.now().isoformat(),
        }

        try:
            # Step 2: Script
            self.logger.info("Step 2/6: Generating script…")
            script = self.scripter.generate(topic)
            result["title"] = script.get("title", "")

            # Step 3: Voiceover
            self.logger.info("Step 3/6: Synthesizing voiceover…")
            audio_path = str(out_dir / "audio.mp3")
            self.voice.synthesize(script, audio_path)
            result["audio_path"] = audio_path

            # Step 4: Video
            self.logger.info("Step 4/6: Rendering video…")
            video_path = str(out_dir / "video.mp4")
            self.video.render(script, audio_path, video_path)
            result["video_path"] = video_path

            # Step 5: Thumbnail
            self.logger.info("Step 5/6: Creating thumbnail…")
            thumb_path = str(out_dir / "thumbnail.jpg")
            self.thumbnail.create(script, thumb_path)
            result["thumbnail_path"] = thumb_path

            # Step 6: Upload (or skip in dry-run)
            if self.dry_run:
                self.logger.info("Step 6/6: DRY RUN — skipping upload")
                result["url"] = f"file://{video_path}"
            else:
                self.logger.info("Step 6/6: Uploading to YouTube…")
                upload_result = self.uploader.publish(video_path, thumb_path, script, slot_index)
                result.update(upload_result)

            result["success"]   = True
            result["completed"] = datetime.now().isoformat()

        except Exception as e:
            result["error"]     = str(e)
            result["traceback"] = traceback.format_exc()
            result["completed"] = datetime.now().isoformat()
            self.logger.error(f"Pipeline error: {e}")
            self.logger.debug(traceback.format_exc())

            if not config.SKIP_ON_FAIL:
                raise

        return result

    def _print_summary(self, results: List[Dict]) -> None:
        ok = [r for r in results if r.get("success")]
        fail = [r for r in results if not r.get("success")]
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"SUMMARY: {len(ok)} succeeded / {len(fail)} failed")
        for r in ok:
            self.logger.info(f"  ✓ {r.get('title', r['topic'])[:55]}")
            self.logger.info(f"    {r.get('url', r.get('video_path', ''))}")
        for r in fail:
            self.logger.info(f"  ✗ {r['topic'][:55]} — {r.get('error', '')[:60]}")
        self.logger.info("="*60)

    def _save_report(self, results: List[Dict]) -> None:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        report_path = f"{config.LOG_DIR}/report_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_path, "w") as f:
            json.dump({
                "run_id": self.run_id,
                "date": datetime.now().isoformat(),
                "dry_run": self.dry_run,
                "provider": config.SCRIPT_MODEL_PROVIDER,
                "results": results,
            }, f, indent=2)
        self.logger.info(f"Report saved: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoTube pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run full pipeline but skip YouTube upload")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of videos to produce (default: 1)")
    parser.add_argument("--topic", type=str, default=None,
                        help="Override topic research with a specific topic")
    args = parser.parse_args()

    orchestrator = Orchestrator(dry_run=args.dry_run)
    results = orchestrator.run(count=args.count, topic_override=args.topic)

    # Exit with error code if nothing succeeded
    if not any(r.get("success") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
