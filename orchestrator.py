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
import asyncio
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
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
        self.uploader   = None  # Lazy-loaded only when needed (render/upload)

    def run_prefetch(self, count: int = 2) -> None:
        """Job 1: Research topics, generate scripts, submit Kling tasks async → Supabase queue."""
        # Pre-flight: harvest any completed Kling videos from existing queue before generating new scripts
        self.logger.info("Pre-flight: Checking for completed Kling tasks in queue...")
        self._harvest_completed_kling_tasks()

        # Check queue level — only prefetch if pending count < 3
        pending_count = self._count_pending_videos()
        if pending_count >= 3:
            self.logger.info(f"Queue full: {pending_count} pending scripts available — skipping prefetch (threshold: 3)")
            return
        self.logger.info(f"Queue status: {pending_count} pending scripts — prefetching {count} more")

        topics = self.research.get_topics(count)
        if not topics:
            self.logger.info("No new topics found")
            return

        queued_count = 0
        for topic in topics[:count]:
            try:
                script = self.scripter.generate(topic)

                # Step 1: Save script to DB immediately — this must succeed before any video work
                row_id = self._save_pending_video(topic["topic"], script, {})
                if not row_id:
                    self.logger.warning(f"Could not get row_id for '{topic['topic']}' — skipping async Kling tasks")
                    queued_count += 1
                    continue

                self.logger.info(f"Queued (script saved): {script.get('title', topic['topic'])[:60]}")

                # Step 2: Submit Kling tasks async (fire-and-forget) — do NOT wait for completion
                try:
                    kling_task_ids = self._submit_kling_tasks_async(
                        script.get("sections", []),
                        script.get("visual_queries", [])
                    )

                    # Step 3: Save task IDs to DB for later polling at render time
                    if kling_task_ids:
                        self._save_kling_task_ids(row_id, kling_task_ids)
                        self.logger.info(f"Submitted {sum(1 for v in kling_task_ids.values() if v)} Kling tasks (will poll at render time)")
                    else:
                        self.logger.info(f"No Kling tasks submitted (videos may be cached or skipped)")

                except Exception as e:
                    self.logger.warning(f"Kling task submission failed (script already saved): {e}")

                queued_count += 1
            except Exception as e:
                self.logger.error(f"Prefetch failed for '{topic['topic']}': {e}")

        self.logger.info(f"Prefetch complete: {queued_count} scripts queued with async Kling tasks")

    def _submit_kling_tasks_async(self, sections: List[Dict], visual_queries: List[str]) -> Dict[int, Optional[str]]:
        """Submit Kling tasks asynchronously for all sections. Returns task_id dict (fires and forgets)."""
        import asyncio
        from agents.kling_video_agent import KlingVideoGenerator

        async def _submit_all():
            try:
                generator = KlingVideoGenerator()
                results = {}

                for i, section in enumerate(sections):
                    query = (
                        visual_queries[i].strip()
                        if i < len(visual_queries) and visual_queries[i].strip()
                        else f"cinematic section {i+1}"
                    )

                    # Submit task (returns task_id or None if cached)
                    task_id = await generator.submit(
                        prompt=query,
                        section_idx=i,
                        duration=5
                    )
                    results[i] = task_id

                await generator.close()
                return results
            except Exception as e:
                self.logger.warning(f"Error submitting Kling tasks: {e}")
                return {}

        # Run async tasks
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(_submit_all())
        except Exception as e:
            self.logger.warning(f"Failed to submit Kling tasks: {e}")
            return {}

    def run_render(self, count: int = 1) -> List[Dict]:
        """Job 2: Pull pending scripts from Supabase queue → voice + video + upload."""
        results = []
        for slot_index in range(count):
            row = self._fetch_pending_video()
            if not row:
                self.logger.info("Queue empty — no pending videos to render")
                break
            result = self._process_queued(row, slot_index)
            results.append(result)
            if result.get("success"):
                self.logger.info(f"  ✓ Rendered & uploaded: {result.get('url', result.get('video_path', ''))}")
            else:
                self.logger.error(f"  ✗ Render failed: {result.get('error', 'unknown')[:80]}")

        self._print_summary(results)
        self._save_report(results)
        return results

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
                uploader = self._get_uploader()
                if uploader:
                    upload_result = uploader.publish(video_path, thumb_path, script, slot_index)
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

    def _process_queued(self, row: Dict, slot_index: int = 0) -> Dict:
        """Process a script from the Supabase queue (skips research + script generation)."""
        job_id = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        out_dir = Path(config.OUTPUT_DIR) / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "job_id":    job_id,
            "topic":     row.get("topic", ""),
            "success":   False,
            "started":   datetime.now().isoformat(),
            "queued_id": row.get("id"),
        }

        try:
            # Update status to rendering
            self._update_pending_status(row["id"], "rendering")

            script = row["script_json"]
            result["title"] = script.get("title", "")

            # Resolve pre-cached image paths back to absolute (if any exist)
            image_cache = {}
            for k, v in (row.get("image_cache") or {}).items():
                if v:
                    abs_path = str(Path.cwd() / v)
                    image_cache[int(k)] = abs_path
                else:
                    image_cache[int(k)] = None

            # If image_cache is empty, pass None so render job generates videos at runtime
            prefetched_images = image_cache if image_cache else None

            # Check for Kling tasks submitted during prefetch — poll briefly (60s timeout)
            kling_task_ids = row.get("kling_task_ids")
            if kling_task_ids:
                self.logger.info(f"Checking {len(kling_task_ids)} pending Kling tasks from prefetch...")
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                try:
                    kling_results = loop.run_until_complete(
                        self._check_kling_tasks(row["id"], kling_task_ids, script)
                    )

                    # Merge Kling results with prefetched images (Kling takes priority)
                    if prefetched_images is None:
                        prefetched_images = {}
                    for section_idx, video_path in kling_results.items():
                        if video_path:
                            prefetched_images[section_idx] = video_path
                            self.logger.info(f"Using Kling video for section {section_idx}")

                except Exception as e:
                    self.logger.warning(f"Error checking Kling tasks: {e} (will generate at runtime)")
            else:
                self.logger.info("No pending Kling tasks found")

            # Step 3: Voiceover
            self.logger.info("Step 3/6: Synthesizing voiceover…")
            audio_path = str(out_dir / "audio.mp3")
            self.voice.synthesize(script, audio_path)
            result["audio_path"] = audio_path

            # Step 4: Video (with prefetched images, or None for runtime generation)
            self.logger.info("Step 4/6: Rendering video…")
            video_path = str(out_dir / "video.mp4")
            self.video.render(script, audio_path, video_path, prefetched_images=prefetched_images)
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
                uploader = self._get_uploader()
                if uploader:
                    upload_result = uploader.publish(video_path, thumb_path, script, slot_index)
                    result.update(upload_result)

            result["success"]   = True
            result["completed"] = datetime.now().isoformat()

            # Update Supabase with success
            self._update_pending_status(
                row["id"],
                "published",
                youtube_url=result.get("url"),
            )

        except Exception as e:
            result["error"]     = str(e)
            result["traceback"] = traceback.format_exc()
            result["completed"] = datetime.now().isoformat()
            self.logger.error(f"Render failed: {e}")
            self.logger.debug(traceback.format_exc())

            # Update Supabase with failure
            self._update_pending_status(row["id"], "failed", error_text=str(e))

            if not config.SKIP_ON_FAIL:
                raise

        return result

    def _save_pending_video(self, topic: str, script: Dict, image_cache: Dict) -> Optional[int]:
        """Insert a pending video into Supabase queue. Returns row id if successful."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            self.logger.warning("Supabase not configured — prefetch skipped")
            return None
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            res = client.table("pending_videos").insert({
                "topic": topic,
                "script_json": script,
                "image_cache": image_cache,
                "status": "pending",
                "approved": True,
            }).execute()
            row_id = res.data[0]["id"] if res.data else None
            self.logger.info(f"Saved to Supabase: {topic} (row_id={row_id})")
            return row_id
        except Exception as e:
            self.logger.error(f"Failed to save pending video to Supabase: {e}")
            raise

    def _fetch_pending_video(self) -> Optional[Dict]:
        """Fetch one pending, approved video from Supabase queue."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            self.logger.warning("Supabase not configured — cannot fetch queue")
            return None
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            res = (
                client.table("pending_videos")
                .select("*")
                .eq("status", "pending")
                .eq("approved", True)
                .order("created_at")
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            self.logger.error(f"Failed to fetch pending video from Supabase: {e}")
            return None

    def _update_pending_status(self, row_id: int, status: str, **kwargs) -> None:
        """Update a pending video's status in Supabase."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            self.logger.warning("Supabase not configured — status update skipped")
            return
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            payload = {"status": status, **kwargs}
            if status == "published":
                payload["published_at"] = datetime.now(tz=timezone.utc).isoformat()
            client.table("pending_videos").update(payload).eq("id", row_id).execute()
            self.logger.info(f"Updated Supabase row {row_id}: status={status}")
        except Exception as e:
            self.logger.error(f"Failed to update Supabase status: {e}")

    def _update_pending_image_cache(self, row_id: int, image_cache: Dict) -> None:
        """Update image_cache on an existing pending_videos row after video pre-generation."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            return
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            client.table("pending_videos").update(
                {"image_cache": image_cache}
            ).eq("id", row_id).execute()
            self.logger.info(f"Updated image_cache for row {row_id}")
        except Exception as e:
            self.logger.warning(f"Failed to update image_cache for row {row_id}: {e}")

    def _count_pending_videos(self) -> int:
        """Count pending, approved videos in Supabase queue."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            self.logger.warning("Supabase not configured — assuming queue is empty")
            return 0
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            res = (
                client.table("pending_videos")
                .select("id", count="exact")
                .eq("status", "pending")
                .eq("approved", True)
                .execute()
            )
            count = res.count if res.count is not None else 0
            return count
        except Exception as e:
            self.logger.error(f"Failed to count pending videos from Supabase: {e}")
            return 0

    def _harvest_completed_kling_tasks(self) -> None:
        """Pre-flight: Check if any pending videos have completed Kling tasks, download and cache them."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            return

        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

            # Fetch all pending videos with kling_task_ids
            res = (
                client.table("pending_videos")
                .select("id, topic, script_json, kling_task_ids, image_cache")
                .not_("kling_task_ids", "is", None)
                .eq("status", "pending")
                .limit(10)  # Don't harvest too many at once
                .execute()
            )

            if not res.data:
                self.logger.info("No pending Kling tasks to harvest")
                return

            self.logger.info(f"Harvesting {len(res.data)} pending Kling tasks...")

            for row in res.data:
                row_id = row["id"]
                topic = row["topic"]
                kling_task_ids = row.get("kling_task_ids", {})
                script = row.get("script_json", {})
                image_cache = row.get("image_cache") or {}

                if not kling_task_ids:
                    continue

                try:
                    # Poll Kling tasks with short timeout (30s)
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                try:
                    kling_results = loop.run_until_complete(
                        self._check_kling_tasks(row_id, kling_task_ids, script, timeout_per_task=30)
                    )

                    # Update image_cache with any newly downloaded videos
                    if kling_results:
                        for section_idx, video_path in kling_results.items():
                            if video_path:
                                try:
                                    rel_path = str(Path(video_path).relative_to(Path.cwd()))
                                except ValueError:
                                    rel_path = str(video_path)
                                image_cache[str(section_idx)] = rel_path
                                self.logger.info(f"[HARVEST] {topic[:40]} section {section_idx}: cached Kling video")

                        # Update DB: new image_cache + clear kling_task_ids (no need to re-check)
                        client.table("pending_videos").update({
                            "image_cache": image_cache,
                            "kling_task_ids": None  # Clear to avoid re-checking at render time
                        }).eq("id", row_id).execute()
                        self.logger.info(f"[HARVEST] Updated cache for {topic[:40]} — {sum(1 for v in image_cache.values() if v)}/6 sections")
                    else:
                        self.logger.info(f"[HARVEST] No completed tasks yet for {topic[:40]}")

                except Exception as e:
                    self.logger.warning(f"[HARVEST] Error checking tasks for {topic[:40]}: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to harvest completed Kling tasks: {e}")

    def _save_kling_task_ids(self, row_id: int, kling_task_ids: Dict[int, Optional[str]]) -> None:
        """Store Kling task IDs in Supabase after async submission."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            return
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            # Filter out None values (cached/skipped sections)
            tasks = {str(k): v for k, v in kling_task_ids.items() if v is not None}
            if tasks:
                client.table("pending_videos").update(
                    {"kling_task_ids": tasks, "kling_submitted_at": datetime.now().isoformat()}
                ).eq("id", row_id).execute()
                self.logger.info(f"Saved {len(tasks)} Kling task IDs for row {row_id}")
            else:
                self.logger.info(f"No Kling task IDs to save (all sections cached/skipped)")
        except Exception as e:
            self.logger.warning(f"Failed to save Kling task IDs for row {row_id}: {e}")

    async def _check_kling_tasks(self, row_id: int, kling_task_ids: Dict[str, str], script: Dict, timeout_per_task: int = 60) -> Dict[int, Optional[str]]:
        """Check and download Kling videos (at render time or during harvest). Default 60s timeout per task."""
        from agents.kling_video_agent import KlingVideoGenerator

        if not kling_task_ids:
            return {}

        try:
            generator = KlingVideoGenerator()
            results = {}

            visual_queries = script.get("visual_queries", [])

            for section_idx_str, task_id in kling_task_ids.items():
                section_idx = int(section_idx_str)
                query = visual_queries[section_idx] if section_idx < len(visual_queries) else "cinematic"

                # Poll with configurable timeout
                path = await generator.check_and_download(
                    task_id=task_id,
                    prompt=query,
                    section_idx=section_idx,
                    duration=5,
                    timeout_seconds=timeout_per_task
                )
                results[section_idx] = path
                if path:
                    log_prefix = "[HARVEST]" if timeout_per_task == 30 else "[KLING-RENDER]"
                    self.logger.info(f"{log_prefix} Section {section_idx}: downloaded {Path(path).name}")
                else:
                    log_prefix = "[HARVEST]" if timeout_per_task == 30 else "[KLING-RENDER]"
                    self.logger.info(f"{log_prefix} Section {section_idx}: not ready in {timeout_per_task}s")

            await generator.close()
            return results

        except Exception as e:
            self.logger.warning(f"Failed to check Kling tasks: {e}")
            return {}

    def _get_uploader(self) -> Optional[UploadAgent]:
        """Lazy-load UploadAgent only when needed (not in dry-run or prefetch modes)."""
        if self.dry_run or self.uploader is not None:
            return self.uploader
        if not self.dry_run:
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
    parser.add_argument("--mode", choices=["prefetch", "render", "auto"], default="auto",
                        help="prefetch=research+script+images only; render=pull queue+produce video; auto=full pipeline (default)")
    args = parser.parse_args()

    orchestrator = Orchestrator(dry_run=args.dry_run)

    if args.mode == "prefetch":
        orchestrator.run_prefetch(count=args.count)
        results = []  # prefetch doesn't return results
    elif args.mode == "render":
        results = orchestrator.run_render(count=args.count)
    else:  # auto
        results = orchestrator.run(count=args.count, topic_override=args.topic)

    # Exit with error code if nothing succeeded
    if results and not any(r.get("success") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
