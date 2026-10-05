"""
AutoTube Orchestrator — pipeline entry point.

Usage:
    python orchestrator.py --dry-run                      # explainer, full pipeline, no upload
    python orchestrator.py --dry-run --topic "..."        # skip research, use this topic
    python orchestrator.py --dry-run --script path.json   # skip research and the LLM
    python orchestrator.py --style kids --dry-run         # "Explained Like You're 5" track
    python orchestrator.py                                # LIVE: uploads to the channel
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from config import config
from agents.research_agent import ResearchAgent
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


def next_utc_time(hhmm: str, now: Optional[datetime] = None, min_lead_minutes: int = 30) -> str:
    """ISO-8601 UTC for the next "HH:MM" at least `min_lead_minutes` from now (YouTube needs a future time)."""
    from datetime import timedelta
    h, m = map(int, hhmm.split(":"))
    now = now or datetime.now(timezone.utc)
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t < now + timedelta(minutes=min_lead_minutes):
        t += timedelta(days=1)
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Orchestrator:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.run_id = uuid.uuid4().hex[:8]
        self.logger = setup_logging(self.run_id)

        # Refuse to run with paid services configured (FREE_ONLY=true by default)
        config.assert_free_only()

        self.logger.info("=== AutoTube Pipeline ===")
        self.logger.info(f"Run ID     : {self.run_id}")
        self.logger.info(f"Mode       : {'DRY RUN (no upload)' if dry_run else 'LIVE'}")
        self.logger.info(f"Style      : {config.VIDEO_STYLE} (free-only: {config.FREE_ONLY})")

        self.research = ResearchAgent()
        self.uploader = None  # Lazy-loaded only when a real upload happens

    def run(self, count: int = 1, topic_override: Optional[str] = None, script_path: Optional[str] = None) -> List[Dict]:
        """Run the full pipeline for `count` videos. Returns list of result dicts."""
        if config.VIDEO_STYLE == "kids":
            return self.run_kids(count, topic_override, script_path)
        return self.run_explainer(count, topic_override, script_path)

    # ── Animated explainer ──────────────────────────────────────────

    def run_explainer(self, count: int = 1, topic_override: Optional[str] = None,
                      script_path: Optional[str] = None) -> List[Dict]:
        """Research → grounded script → Remotion render → QA → private upload.
        A topic is recorded in history only after its video uploads successfully."""
        self._cleanup_old_outputs(max_age_days=1)
        if script_path:
            with open(script_path) as f:
                fixed = json.load(f)
            topics = [{"topic": fixed.get("topic") or fixed.get("title", "script"), "script": fixed}]
        elif topic_override:
            topics = [{"topic": topic_override, "source": "manual_override", "url": ""}]
        else:
            self.logger.info("Step 1/5: Researching topics…")
            topics = self.research.get_topics(count, record=False)
        if not topics:
            self.logger.error("No topics found — aborting")
            return []

        results = []
        for i, topic in enumerate(topics[:count]):
            self.logger.info(f"\n{'─'*60}\nVideo {i+1}/{count}: {topic['topic'][:70]}")
            result = self._process_explainer(topic)
            results.append(result)
            if result.get("success"):
                self.logger.info(f"  ✓ Done: {result.get('url', result.get('video_path', ''))}")
            else:
                self.logger.error(f"  ✗ Failed: {result.get('error', 'unknown')[:200]}")
        self._print_summary(results)
        self._save_report(results)
        return results

    def _process_explainer(self, topic: Dict) -> Dict:
        from agents.explainer_agent import ExplainerAgent, description_with_chapters
        from agents.explainer_script_agent import ExplainerScriptAgent

        job_id = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        out_dir = Path(config.OUTPUT_DIR) / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        result = {"job_id": job_id, "topic": topic["topic"], "style": "explainer", "success": False,
                  "started": datetime.now().isoformat()}
        try:
            self.logger.info("Step 2/5: Writing grounded script (free LLM)…")
            script = topic.get("script") or ExplainerScriptAgent().generate(topic)
            (out_dir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
            result["title"] = script.get("title", "")
            result["fact_flags"] = script.get("fact_flags", [])
            if result["fact_flags"]:
                self.logger.warning(f"  {len(result['fact_flags'])} number(s) not found in the source — review before publishing")

            self.logger.info("Step 3/5: Voice + animation render + QA…")
            min_len = config.EXPLAINER_MIN_SECONDS if not topic.get("script") else None
            rendered = ExplainerAgent().render(script, str(out_dir), min_duration=min_len)
            result.update({"video_path": rendered["video_path"], "thumbnail_path": rendered["thumbnail_path"],
                           "duration": rendered["duration"], "chapters": rendered["chapters"]})

            upload_script = {
                "title": script["title"],
                "description": description_with_chapters(script.get("description", ""), rendered["chapters"],
                                                          script.get("sources", [])),
                "tags": script.get("tags", []),
            }
            if self.dry_run:
                self.logger.info("Step 4/5: DRY RUN — skipping upload")
                result["url"] = f"file://{rendered['video_path']}"
            else:
                self.logger.info(f"Step 4/5: Uploading to YouTube ({config.VIDEO_PRIVACY})…")
                uploader = self._get_uploader()
                if not uploader:
                    raise RuntimeError("YouTube uploader unavailable (check credentials)")
                publish_at = next_utc_time(config.EXPLAINER_PUBLISH_AT_UTC) if config.EXPLAINER_PUBLISH_AT_UTC else None
                if publish_at:
                    self.logger.info(f"  scheduled to go public at {publish_at} (private until then — review it in Studio)")
                up = uploader.publish(rendered["video_path"], rendered["thumbnail_path"], upload_script,
                                      publish_at=publish_at, playlist=config.EXPLAINER_PLAYLIST)
                result.update(up)
                if up.get("success") is False:
                    raise RuntimeError(f"upload failed: {up.get('error', '')}")
                self.logger.info("Step 5/5: Recording topic as used")
                if not topic.get("script"):
                    self.research.mark_used([topic])
            result["success"] = True
        except Exception as e:  # noqa: BLE001 — one failed video must not stop the run
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            self.logger.error(f"Explainer pipeline error: {e}")
        result["completed"] = datetime.now().isoformat()
        (out_dir / "result.json").write_text(json.dumps({k: v for k, v in result.items() if k != "traceback"},
                                                         indent=2, default=str))
        return result

    # ── Kids track: "Explained Like You're 5" ─────────────────────────────────

    def run_kids(self, count: int = 1, topic_override: Optional[str] = None,
                 script_path: Optional[str] = None) -> List[Dict]:
        """Headline→concept (or bank) topic → analogy script → story-kit render → QA → private upload.
        A topic is recorded in data/kids_topics_history.json only after its video uploads."""
        from agents.kids_topic_agent import KidsTopicAgent

        self._cleanup_old_outputs(max_age_days=1)
        topics_agent = KidsTopicAgent()
        if script_path:
            with open(script_path) as f:
                fixed = json.load(f)
            topics = [{"topic": fixed.get("topic") or fixed.get("title", "script"), "script": fixed}]
        elif topic_override:
            topics = [{"topic": topic_override, "source": "manual_override", "area": ""}]
        else:
            self.logger.info("Step 1/5: Picking a kids topic (headlines → big idea, bank fallback)…")
            topics = topics_agent.get_topics(count)
        if not topics:
            self.logger.error("No kids topics found — aborting")
            return []
        results = []
        for i, topic in enumerate(topics[:count]):
            self.logger.info(f"\n{'─'*60}\nKids video {i+1}/{count}: {topic['topic'][:70]}")
            result = self._process_kids(topic, topics_agent)
            results.append(result)
            if result.get("success"):
                self.logger.info(f"  ✓ Done: {result.get('url', result.get('video_path', ''))}")
            else:
                self.logger.error(f"  ✗ Failed: {result.get('error', 'unknown')[:200]}")
        self._print_summary(results)
        self._save_report(results)
        return results

    def _process_kids(self, topic: Dict, topics_agent) -> Dict:
        from agents.kids_agent import KidsAgent, description_for
        from agents.kids_script_agent import KidsScriptAgent

        job_id = f"{datetime.now().strftime('%Y%m%d')}_kids_{uuid.uuid4().hex[:6]}"
        out_dir = Path(config.OUTPUT_DIR) / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        result = {"job_id": job_id, "topic": topic["topic"], "style": "kids", "success": False,
                  "started": datetime.now().isoformat()}
        try:
            self.logger.info("Step 2/5: Writing the story script (free LLM: plan → script → check)…")
            script = topic.get("script") or KidsScriptAgent().generate(topic)
            (out_dir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
            result["title"] = script.get("title", "")
            result["review"] = script.get("review", {})

            self.logger.info("Step 3/5: Voice + story animation + QA…")
            rendered = KidsAgent().render(script, str(out_dir), enforce_length=not topic.get("script"))
            result.update({"video_path": rendered["video_path"], "thumbnail_path": rendered["thumbnail_path"],
                           "duration": rendered["duration"], "contact_sheet": rendered["contact_sheet"]})
            upload_script = {"title": script["title"], "description": description_for(script),
                             "tags": script.get("tags", [])}
            if self.dry_run:
                self.logger.info("Step 4/5: DRY RUN — skipping upload")
                result["url"] = f"file://{rendered['video_path']}"
            else:
                self.logger.info(f"Step 4/5: Uploading to YouTube ({config.VIDEO_PRIVACY}, not made for kids)…")
                uploader = self._get_uploader()
                if not uploader:
                    raise RuntimeError("YouTube uploader unavailable (check credentials)")
                publish_at = next_utc_time(config.KIDS_PUBLISH_AT_UTC) if config.KIDS_PUBLISH_AT_UTC else None
                if publish_at:
                    self.logger.info(f"  scheduled to go public at {publish_at} (private until then — review it in Studio)")
                up = uploader.publish(rendered["video_path"], rendered["thumbnail_path"], upload_script,
                                      publish_at=publish_at, playlist=config.KIDS_PLAYLIST)
                result.update(up)
                if up.get("success") is False:
                    raise RuntimeError(f"upload failed: {up.get('error', '')}")
                self.logger.info("Step 5/5: Recording topic as used")
                if not topic.get("script"):
                    topics_agent.mark_used([topic])
                if rendered.get("short_path"):
                    result["short"] = self._upload_kids_short(uploader, rendered["short_path"], upload_script,
                                                              up.get("url", ""))
            result["success"] = True
        except Exception as e:  # noqa: BLE001 — one failed video must not stop the run
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            self.logger.error(f"Kids pipeline error: {e}")
        result["completed"] = datetime.now().isoformat()
        (out_dir / "result.json").write_text(json.dumps({k: v for k, v in result.items() if k != "traceback"},
                                                         indent=2, default=str))
        return result

    def _upload_kids_short(self, uploader, short_path: str, full: Dict, full_url: str) -> Dict:
        """Upload the vertical cut as a second video (a YouTube Short). The full video is already
        up, so a failure here is logged and reported but never fails the run."""
        try:
            from agents.kids_agent import short_meta

            when = config.KIDS_SHORT_PUBLISH_AT_UTC or config.KIDS_PUBLISH_AT_UTC
            publish_at = next_utc_time(when) if when else None
            short = short_meta(full, full_url)
            self.logger.info(f"Uploading the Short ({'public at ' + publish_at if publish_at else config.VIDEO_PRIVACY})…")
            up = uploader.publish(short_path, None, short, publish_at=publish_at)
            if up.get("success") is False:
                self.logger.warning(f"  Short upload failed: {up.get('error', '')}")
            else:
                self.logger.info(f"  ✓ Short: {up.get('url', '')}")
            return up
        except Exception as e:  # noqa: BLE001
            self.logger.warning(f"  Short upload failed: {e}")
            return {"success": False, "error": str(e)}

    def _cleanup_old_outputs(self, max_age_days: float = 1) -> None:
        """Delete output directories older than max_age_days (all of them if the disk is nearly full)."""
        try:
            outputs_dir = Path(config.OUTPUT_DIR)
            if not outputs_dir.exists():
                return
            low_disk = shutil.disk_usage("/").free / (1024**3) < 2.0
            if low_disk:
                self.logger.warning("LOW DISK: under 2 GB free — deleting all old outputs")
            now = time.time()
            deleted = []
            for item in outputs_dir.iterdir():
                if not item.is_dir():
                    continue
                if not low_disk and (now - item.stat().st_mtime) / 86400 < max_age_days:
                    continue
                try:
                    shutil.rmtree(item)
                    deleted.append(item.name)
                except Exception as e:
                    self.logger.warning(f"Failed to delete {item.name}: {e}")
            if deleted:
                self.logger.info(f"[CLEANUP] Deleted {len(deleted)} old output dirs: {', '.join(deleted)}")
        except Exception as e:
            self.logger.warning(f"Auto-cleanup failed: {e}")

    def _get_uploader(self) -> Optional[UploadAgent]:
        """Lazy-load UploadAgent only when needed (never in a dry run)."""
        if self.dry_run or self.uploader is not None:
            return self.uploader
        self.uploader = UploadAgent()
        return self.uploader


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
    parser.add_argument("--style", choices=["explainer", "kids"], default=None,
                        help="Video style (default: VIDEO_STYLE env / config, 'explainer'); "
                             "'kids' = Explained Like You're 5 (2-3 min story videos)")
    parser.add_argument("--script", type=str, default=None,
                        help="Render this script JSON (skips research + LLM), e.g. tests/fixtures/explainer_script.json "
                             "or tests/fixtures/kids_stock_market.json")
    args = parser.parse_args()
    if args.style:
        config.VIDEO_STYLE = args.style

    orchestrator = Orchestrator(dry_run=args.dry_run)
    results = orchestrator.run(count=args.count, topic_override=args.topic, script_path=args.script)

    # Exit with error code if nothing succeeded
    if results and not any(r.get("success") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
