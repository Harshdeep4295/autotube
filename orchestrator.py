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

# Google Cloud Platform libraries (imported conditionally for Cloud Run)
try:
    from google.cloud import storage, firestore, secretmanager
    from google.api_core.exceptions import NotFound, PermissionDenied
    HAS_GCP = True
except ImportError:
    HAS_GCP = False

from config import config
from agents.research_agent import ResearchAgent
from agents.script_agent import ScriptAgent
from agents.voice_agent import VoiceAgent
from agents.video_agent import VideoAgent
from agents.thumbnail_agent import ThumbnailAgent
from agents.upload_agent import UploadAgent
from agents.gcp_cost_tracker import GCPCostTracker


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


def load_secrets_from_gcp(run_id: str, logger: logging.Logger) -> None:
    """Load secrets from GCP Secret Manager and set as environment variables."""
    if not HAS_GCP:
        logger.info("GCP libraries not installed — using .env (local mode)")
        return

    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        logger.info("GCP_PROJECT_ID not set — using .env (local mode)")
        return

    logger.info(f"Loading secrets from GCP Secret Manager (project: {project_id})")

    client = secretmanager.SecretManagerServiceClient()
    secret_keys = [
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "YOUTUBE_TOKEN_JSON",
        "YOUTUBE_CLIENT_SECRETS",
        "PEXELS_API_KEY",
        "AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
    ]

    loaded_count = 0
    for secret_name in secret_keys:
        try:
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            os.environ[secret_name] = secret_value

            # Map SUPABASE_ANON_KEY to SUPABASE_KEY for config compatibility
            if secret_name == "SUPABASE_ANON_KEY":
                os.environ["SUPABASE_KEY"] = secret_value

            loaded_count += 1
            logger.info(f"  ✓ Loaded {secret_name}")
        except NotFound:
            logger.warning(f"  ✗ Secret not found: {secret_name}")
        except PermissionDenied:
            logger.error(f"  ✗ Permission denied accessing: {secret_name}")
        except Exception as e:
            logger.warning(f"  ✗ Error loading {secret_name}: {e}")

    logger.info(f"Loaded {loaded_count}/{len(secret_keys)} secrets from GCP")


class Orchestrator:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.run_id = uuid.uuid4().hex[:8]
        self.logger = setup_logging(self.run_id)

        # Load secrets from GCP Secret Manager (Cloud Run only, skipped locally)
        load_secrets_from_gcp(self.run_id, self.logger)

        # Initialize Cloud Storage client if in Cloud Run
        self.gcs_client = None
        self.gcs_bucket = None
        if HAS_GCP and os.getenv("GCP_PROJECT_ID") and os.getenv("GCS_BUCKET_NAME"):
            try:
                self.gcs_client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
                self.gcs_bucket = self.gcs_client.bucket(os.getenv("GCS_BUCKET_NAME", "autotube-veo-output"))
                self.logger.info(f"Cloud Storage initialized: {self.gcs_bucket.name}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Cloud Storage: {e}")

        # Initialize Firestore client if in Cloud Run
        self.firestore_client = None
        if HAS_GCP and os.getenv("GCP_PROJECT_ID"):
            try:
                self.firestore_client = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
                self.logger.info(f"Firestore initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Firestore: {e}")

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

        # Pre-flight: Cleanup old outputs to ensure disk space
        self._cleanup_old_outputs(max_age_days=1)

        # Pre-flight: Retry failed uploads from GCS before generating new videos
        self.logger.info("Pre-flight: Checking for pending uploads from GCS…")
        gcs_results = self._retry_pending_uploads()
        results.extend(gcs_results)

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

        # Final cleanup after all uploads complete
        if any(r.get("success") for r in results):
            self._cleanup_old_outputs(max_age_days=1)

        return results

    def run(self, count: int = 1, topic_override: Optional[str] = None) -> List[Dict]:
        """Run the full pipeline for `count` videos. Returns list of result dicts."""

        # Pre-flight: Ensure background music library is stocked
        try:
            from agents.music_agent import ensure_music_available
            ensure_music_available(min_tracks=5)
        except Exception:
            pass

        # Pre-flight: Cleanup old outputs to ensure disk space
        self._cleanup_old_outputs(max_age_days=1)

        # Step 0: Auto-approve expired scripts, then check queue
        self._auto_approve_expired()

        if not topic_override:
            self.logger.info("Step 1/6: Checking for pending videos in queue…")
            pending_scripts = self._fetch_pending_scripts_for_render(count)
            if pending_scripts:
                self.logger.info(f"Found {len(pending_scripts)} pending script(s) in queue — skipping API research")
                return self._process_pending_scripts(pending_scripts)

        # Step 1: Research topics (only if queue is empty or topic_override is set)
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

        # Post-run: Pull analytics metrics (non-blocking)
        if any(r.get("success") for r in results):
            try:
                from agents.analytics_agent import AnalyticsAgent
                AnalyticsAgent().pull_metrics()
            except Exception:
                pass

        # Final cleanup after all uploads complete
        if any(r.get("success") for r in results):
            self._cleanup_old_outputs(max_age_days=1)

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

            # DRY RUN: Load most recent script instead of generating
            if self.dry_run:
                script_path = self._get_latest_script_path()
                if script_path and script_path.exists():
                    with open(script_path) as f:
                        script = json.load(f)
                    self.logger.info(f"  [DRY RUN] Loaded script from {script_path.name}")
                else:
                    script = self.scripter.generate(topic)
                    self.logger.info(f"  [DRY RUN] No previous script found, generated new one")
            else:
                script = self.scripter.generate(topic)

            result["title"] = script.get("title", "")

            # Save script for future dry-run testing
            script_file = out_dir / "script.json"
            with open(script_file, "w") as f:
                json.dump(script, f, indent=2)
            self.logger.info(f"  ✓ Script saved to {script_file.name}")

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

            # If in Cloud Run, upload video to Cloud Storage
            if self.gcs_bucket:
                try:
                    job_id_safe = job_id.replace("/", "_")
                    gcs_video = self._write_output_to_cloud(
                        video_path,
                        f"videos/{job_id_safe}/video.mp4"
                    )
                    if gcs_video:
                        result["gcs_video_path"] = gcs_video
                except Exception as e:
                    self.logger.warning(f"Cloud Storage upload skipped: {e}")

            # Log to Firestore for monitoring/audit trail
            self._log_to_firestore(result)

            # Auto-cleanup old outputs and cache after successful upload
            if result.get("success") and not self.dry_run:
                self._cleanup_old_outputs(max_age_days=1)

        except Exception as e:
            result["error"]     = str(e)
            result["traceback"] = traceback.format_exc()
            result["completed"] = datetime.now().isoformat()
            self.logger.error(f"Pipeline error: {e}")
            self.logger.debug(traceback.format_exc())

            if not config.SKIP_ON_FAIL:
                raise

        return result

    def run_shorts_from_existing(self, pick_strategy: str = "recent_high_views", batch: int = 1) -> List[Dict]:
        """
        Convert existing videos from data/posted_videos.json to Shorts format (9:16).

        Strategies:
        - recent_high_views: Top video from last 7 days
        - all_time_best: Highest-viewed video (rotates through top 10)
        - underutilized: Low-view videos getting second life
        - manual: Specific video ID via --topic override
        """
        # Pre-flight: Cleanup old outputs to ensure disk space
        self._cleanup_old_outputs(max_age_days=1)

        import json
        from pathlib import Path
        from datetime import timedelta

        results = []

        # Load existing videos
        posted_file = Path(config.POSTED_FILE)
        if not posted_file.exists():
            self.logger.error("No posted_videos.json found — no existing videos to convert")
            return results

        with open(posted_file) as f:
            posted = json.load(f)

        if not posted:
            self.logger.error("posted_videos.json is empty — nothing to convert")
            return results

        self.logger.info(f"Loaded {len(posted)} existing videos for Shorts conversion")

        # Pick videos based on strategy
        videos_to_convert = []

        # Build a larger candidate pool so we can fall through on download failures
        CANDIDATE_POOL = max(batch * 5, 10)

        if pick_strategy == "recent_high_views":
            # Top videos from last 7 days, then fall through to older ones
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            recent = [v for v in posted if v.get("uploaded_at", "") > cutoff]
            candidates = (recent + [v for v in posted if v not in recent])[:CANDIDATE_POOL]

        elif pick_strategy == "all_time_best":
            candidates = posted[:CANDIDATE_POOL]

        elif pick_strategy == "underutilized":
            candidates = posted[-CANDIDATE_POOL:]

        else:
            candidates = []

        if not candidates:
            self.logger.warning(f"No videos matched strategy '{pick_strategy}'")
            return results

        self.logger.info(f"Converting {batch} video(s) to Shorts format (pool: {len(candidates)} candidates)")

        # Try candidates in order until we get `batch` successes
        succeeded = 0
        for video in candidates:
            if succeeded >= batch:
                break
            try:
                result = self._convert_to_shorts(video)
                results.append(result)
                succeeded += 1
            except Exception as e:
                self.logger.warning(f"Skipping '{video.get('title', 'Unknown')}': {e} — trying next candidate")
                results.append({
                    "success": False,
                    "original_video_id": video.get("video_id"),
                    "title": video.get("title", ""),
                    "error": str(e),
                    "mode": "shorts_from_existing"
                })

        if succeeded == 0:
            self.logger.error(f"All {len(candidates)} candidates failed — no Shorts produced")

        return results

    def _convert_to_shorts(self, video: Dict) -> Dict:
        """Convert a single video to Shorts format (9:16) and upload."""
        import subprocess
        from moviepy import VideoFileClip

        video_id = video.get("video_id", "")
        title = video.get("title", "Unknown")

        if not video_id:
            raise ValueError(f"Video {title} has no video_id")

        self.logger.info(f"Processing: {title}")

        # Create output directory
        job_id = f"shorts_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        out_dir = Path(config.OUTPUT_DIR) / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Download video from YouTube
            yt_url = f"https://www.youtube.com/watch?v={video_id}"
            self.logger.info(f"  Downloading from {yt_url}...")
            downloaded_path = str(out_dir / "downloaded.mp4")

            # Use ffmpeg to download (requires yt-dlp or similar)
            cmd = [
                "ffmpeg", "-y", "-i", yt_url,
                "-c", "copy", "-bsf:a", "aac_adtstoasc",
                downloaded_path
            ]

            try:
                subprocess.run(cmd, capture_output=True, timeout=300, check=True)
            except Exception as e:
                self.logger.warning(f"FFmpeg download failed, trying alternative method: {e}")
                # Fallback: try using yt-dlp if available
                try:
                    import yt_dlp
                    ydl_opts = {
                        "outtmpl": str(out_dir / "downloaded.mp4"),
                        "quiet": True,
                        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    }
                    # Use cookies file if present (needed when YouTube requires sign-in)
                    cookies_path = Path("cookies.txt")
                    if cookies_path.exists():
                        ydl_opts["cookiefile"] = str(cookies_path)
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(yt_url, download=False)
                        if info is None:
                            raise RuntimeError("Video metadata unavailable — video may be private or deleted")
                        ydl.download([yt_url])
                except Exception as e2:
                    self.logger.error(f"Both download methods failed: {e2}")
                    raise RuntimeError(f"Failed to download video: {e2}")

            if not Path(downloaded_path).exists():
                raise RuntimeError("Download failed - no file created")

            # Step 2: Extract best 60-90s clip (middle section of video)
            self.logger.info(f"  Extracting 60-90s clip...")
            clip = VideoFileClip(downloaded_path)
            duration = clip.duration

            # Extract from middle of video (skip first 10s)
            start_time = max(10, duration / 2 - 45)
            end_time = min(start_time + 75, duration)

            if end_time - start_time < 60:
                # If video is shorter than 60s, use full video
                clipped = clip
                self.logger.info(f"  Video shorter than 60s, using full {duration:.1f}s")
            else:
                clipped = clip.subclipped(start_time, end_time)
                self.logger.info(f"  Extracted {clipped.duration:.1f}s clip ({start_time:.1f}s-{end_time:.1f}s)")

            # Step 3: Re-encode to 1080×1920 Shorts format
            self.logger.info(f"  Re-encoding to 1080×1920 Shorts format...")
            shorts_video_path = str(out_dir / "shorts_video.mp4")

            # Resize to 1080×1920 (maintain aspect, pillarbox if needed)
            w, h = clipped.size
            target_w, target_h = 1080, 1920

            if w / h < target_w / target_h:
                # Pillarbox (narrow video)
                new_w = int(h * (target_w / target_h))
                resized = clipped.resized(new_size=(new_w, h))
                # Center crop to 1080×1920
                x_offset = (new_w - target_w) // 2
                resized = resized.cropped(x1=x_offset, y1=0, x2=x_offset+target_w, y2=target_h)
            else:
                # Letterbox (wide video)
                new_h = int(w * (target_h / target_w))
                resized = clipped.resized(new_size=(w, new_h))
                # Center crop to 1080×1920
                y_offset = (new_h - target_h) // 2
                resized = resized.cropped(x1=0, y1=y_offset, x2=target_w, y2=y_offset+target_h)

            # Use ffmpeg streaming for efficient encoding
            resized.write_videofile(shorts_video_path, codec="libx264", audio_codec="aac", preset="ultrafast", fps=24)
            self.logger.info(f"  ✓ Shorts video saved: {shorts_video_path}")

            # Step 4: Generate minimal script for upload
            shorts_script = {
                "title": f"{title} #Shorts",
                "description": f"Short-form version of '{title}'\n\n#Shorts #YouTube",
                "tags": list(set(video.get("tags", []) + ["Shorts", "Short"])),
                "sections": [],
            }

            # Step 5: Create thumbnail for Shorts (1080×1920)
            thumbnail_path = str(out_dir / "thumbnail.jpg")
            self.thumbnail.create(shorts_script, thumbnail_path)

            # Step 6: Upload as Shorts
            if self.dry_run:
                self.logger.info(f"  [DRY RUN] Would upload to YouTube")
                shorts_video_id = f"shorts_{video_id}"
            else:
                self.logger.info(f"  Uploading to YouTube as Shorts...")
                uploader = self._get_uploader()
                if uploader:
                    upload_result = uploader.publish(
                        shorts_video_path,
                        thumbnail_path,
                        shorts_script,
                        slot_index=0,
                        publish_immediately=True
                    )
                    shorts_video_id = upload_result.get("video_id", f"shorts_{video_id}")
                    if not upload_result.get("success"):
                        raise RuntimeError(f"Upload failed: {upload_result.get('error')}")
                else:
                    raise RuntimeError("Uploader not available")

            self.logger.info(f"  ✓ Shorts uploaded: https://youtube.com/watch?v={shorts_video_id}")

            return {
                "success": True,
                "original_video_id": video_id,
                "shorts_video_id": shorts_video_id,
                "title": title,
                "shorts_path": shorts_video_path,
                "mode": "shorts_from_existing",
                "job_id": job_id,
            }

        finally:
            # Cleanup temporary files
            try:
                clip.close()
            except:
                pass

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

            # If in Cloud Run, upload video to Cloud Storage
            if self.gcs_bucket:
                try:
                    job_id_safe = job_id.replace("/", "_")
                    gcs_video = self._write_output_to_cloud(
                        video_path,
                        f"videos/{job_id_safe}/video.mp4"
                    )
                    if gcs_video:
                        result["gcs_video_path"] = gcs_video
                except Exception as e:
                    self.logger.warning(f"Cloud Storage upload skipped: {e}")

            # Log to Firestore for monitoring/audit trail
            self._log_to_firestore(result)

            # Auto-cleanup old outputs and cache after successful upload
            if result.get("success") and not self.dry_run:
                self._cleanup_old_outputs(max_age_days=1)

            # Update Supabase with success
            self._update_pending_status(
                row["id"],
                "published",
                youtube_url=result.get("url"),
            )

            # Notify via WhatsApp
            if config.WHATSAPP_ENABLED:
                try:
                    from agents.whatsapp_agent import WhatsAppAgent
                    WhatsAppAgent().send_status_update(
                        result.get("title", "Video"),
                        "published",
                        result.get("url", ""),
                    )
                except Exception:
                    pass

        except Exception as e:
            result["error"]     = str(e)
            result["traceback"] = traceback.format_exc()
            result["completed"] = datetime.now().isoformat()
            self.logger.error(f"Render failed: {e}")
            self.logger.debug(traceback.format_exc())

            # Update Supabase with failure
            self._update_pending_status(row["id"], "failed", error_text=str(e))

            # Notify via WhatsApp
            if config.WHATSAPP_ENABLED:
                try:
                    from agents.whatsapp_agent import WhatsAppAgent
                    WhatsAppAgent().send_status_update(
                        row.get("topic", "Video"), "failed"
                    )
                except Exception:
                    pass

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

            auto_approve = not config.APPROVAL_REQUIRED
            res = client.table("pending_videos").insert({
                "topic": topic,
                "script_json": script,
                "image_cache": image_cache,
                "status": "pending",
                "approved": auto_approve,
            }).execute()
            row_id = res.data[0]["id"] if res.data else None
            self.logger.info(f"Saved to Supabase: {topic} (row_id={row_id}, approved={auto_approve})")

            if not auto_approve and config.WHATSAPP_ENABLED:
                try:
                    from agents.whatsapp_agent import WhatsAppAgent
                    wa = WhatsAppAgent()
                    wa.send_approval_request(row_id, script)
                except Exception as wa_err:
                    self.logger.warning(f"WhatsApp notification failed (non-blocking): {wa_err}")

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

    def _auto_approve_expired(self) -> int:
        """Auto-approve scripts that have been pending longer than APPROVAL_TIMEOUT_HOURS."""
        if not config.APPROVAL_REQUIRED:
            return 0
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            return 0
        try:
            from supabase import create_client
            from datetime import datetime, timezone, timedelta

            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=config.APPROVAL_TIMEOUT_HOURS)).isoformat()

            res = (
                client.table("pending_videos")
                .select("id, topic, created_at")
                .eq("status", "pending")
                .eq("approved", False)
                .lt("created_at", cutoff)
                .execute()
            )

            if not res.data:
                return 0

            ids = [r["id"] for r in res.data]
            client.table("pending_videos").update(
                {"approved": True}
            ).in_("id", ids).execute()

            self.logger.info(
                f"Auto-approved {len(ids)} scripts (older than {config.APPROVAL_TIMEOUT_HOURS}h): "
                f"{[r['topic'][:30] for r in res.data]}"
            )

            if config.WHATSAPP_ENABLED:
                try:
                    from agents.whatsapp_agent import WhatsAppAgent
                    titles = [r["topic"][:40] for r in res.data]
                    WhatsAppAgent()._send_message(
                        f"⏰ *Auto-approved {len(ids)} script(s)* (no response in {config.APPROVAL_TIMEOUT_HOURS}h):\n"
                        + "\n".join(f"• {t}" for t in titles)
                    )
                except Exception:
                    pass

            return len(ids)
        except Exception as e:
            self.logger.error(f"Auto-approve check failed: {e}")
            return 0

    def _fetch_pending_scripts_for_render(self, count: int = 1) -> List[Dict]:
        """Fetch up to `count` pending scripts from Supabase queue for rendering."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            return []
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            res = (
                client.table("pending_videos")
                .select("*")
                .eq("status", "pending")
                .eq("approved", True)
                .order("created_at")
                .limit(count)
                .execute()
            )
            return res.data if res.data else []
        except Exception as e:
            self.logger.error(f"Failed to fetch pending scripts: {e}")
            return []

    def _process_pending_scripts(self, scripts: List[Dict]) -> List[Dict]:
        """Process pending scripts from database without research or generation."""
        results = []
        for i, row in enumerate(scripts):
            try:
                script = row.get("script_json", {})
                topic = row.get("topic", "Unknown")
                row_id = row.get("id")

                self.logger.info(f"\n{'─'*60}")
                self.logger.info(f"Video {i+1}/{len(scripts)}: {topic[:60]} (from queue)")

                result = {
                    "job_id": f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
                    "topic": topic,
                    "success": False,
                    "started": datetime.now().isoformat(),
                    "title": script.get("title", topic),
                    "row_id": row_id,
                }

                out_dir = Path(config.OUTPUT_DIR) / result["job_id"]
                out_dir.mkdir(parents=True, exist_ok=True)

                # Skip research & generation — use script directly from queue
                self.logger.info("(Using queued script — skipping research & generation)")

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

                # Step 6: Upload
                self.logger.info("Step 6/6: Uploading to YouTube…")
                uploader = self._get_uploader()
                if uploader:
                    upload_result = uploader.publish(video_path, thumb_path, script, i)
                    result.update(upload_result)

                result["success"] = True
                result["completed"] = datetime.now().isoformat()

                # Mark as published in database
                if row_id:
                    self._update_pending_status(row_id, "published")

                # Log to Firestore
                self._log_to_firestore(result)

                results.append(result)
                if result.get("success"):
                    self.logger.info(f"  ✓ Done: {result.get('url', result.get('video_path', ''))}")
                else:
                    self.logger.error(f"  ✗ Failed: {result.get('error', 'unknown')[:80]}")

            except Exception as e:
                self.logger.error(f"Failed to process pending script '{row.get('topic')}': {e}")
                results.append({
                    "topic": row.get("topic", "Unknown"),
                    "success": False,
                    "error": str(e),
                })

        self._print_summary(results)
        self._save_report(results)
        return results

    def _harvest_completed_kling_tasks(self) -> None:
        """Pre-flight: Check if any pending videos have completed Kling tasks, download and cache them."""
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            return

        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

            # Fetch all pending videos and filter for those with kling_task_ids
            res = (
                client.table("pending_videos")
                .select("id, topic, script_json, kling_task_ids, image_cache")
                .eq("status", "pending")
                .limit(10)  # Don't harvest too many at once
                .execute()
            )

            # Filter for rows with kling_task_ids
            rows_with_tasks = [r for r in res.data if r.get("kling_task_ids")]

            if not rows_with_tasks:
                self.logger.info("No pending Kling tasks to harvest")
                return

            self.logger.info(f"Harvesting {len(rows_with_tasks)} pending Kling tasks...")

            for row in rows_with_tasks:
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

    def _retry_pending_uploads(self) -> List[Dict]:
        """Retry uploading videos from GCS that failed previously."""
        from agents.gcs_backup_agent import GCSBackupAgent
        from google.cloud import storage
        import tempfile

        results = []
        try:
            backup = GCSBackupAgent()
            pending = backup.get_pending_uploads()

            if not pending:
                self.logger.info("No pending uploads in GCS — all caught up")
                return results

            self.logger.info(f"Found {len(pending)} pending uploads — retrying…")
            uploader = self._get_uploader()
            if not uploader:
                self.logger.warning("Uploader not available — cannot retry uploads")
                return results

            for entry in pending[:5]:  # Retry up to 5 per run to avoid timeout
                gcs_path = entry.get("gcs_path", "")
                title = entry.get("title", "")
                attempt = entry.get("attempts", 0) + 1

                try:
                    # Download from GCS to temp file
                    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                        tmp_path = tmp.name

                    self.logger.info(f"Retrying upload ({attempt}): {title[:60]}")
                    storage_client = backup.gcs_client
                    bucket = storage_client.bucket(backup.bucket_name)
                    blob = bucket.blob(gcs_path)
                    blob.download_to_filename(tmp_path)

                    # Retry YouTube upload
                    upload_result = uploader.publish(
                        tmp_path,
                        thumb_path="",  # No thumbnail for retry
                        script={
                            "title": title,
                            "description": entry.get("description", ""),
                            "tags": entry.get("tags", []),
                        },
                        gcs_path=gcs_path,  # Mark as GCS retry
                    )

                    if upload_result.get("success"):
                        self.logger.info(f"  ✓ Retry succeeded: {upload_result.get('url', '')}")
                    else:
                        # Update attempt count for next retry
                        backup.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(backup.manifest_path) as f:
                            manifest = json.load(f)
                        for m in manifest:
                            if m.get("gcs_path") == gcs_path:
                                m["attempts"] = attempt
                                m["last_retry"] = datetime.utcnow().isoformat()
                        with open(backup.manifest_path, "w") as f:
                            json.dump(manifest, f, indent=2)

                    results.append(upload_result)
                    Path(tmp_path).unlink(missing_ok=True)

                except Exception as e:
                    self.logger.warning(f"Retry failed for {title[:60]}: {e}")
                    results.append({"success": False, "error": str(e), "title": title})

        except Exception as e:
            self.logger.warning(f"GCS retry pre-flight failed: {e}")

        return results

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

    def _get_latest_script_path(self) -> Optional[Path]:
        """Find the most recent script.json in outputs/ for dry-run testing."""
        outputs_dir = Path(config.OUTPUT_DIR)
        if not outputs_dir.exists():
            return None
        scripts = list(outputs_dir.glob("*/script.json"))
        if not scripts:
            return None
        return max(scripts, key=lambda p: p.parent.stat().st_mtime)

    def _write_output_to_cloud(self, local_path: str, cloud_relative_path: str) -> Optional[str]:
        """Upload a local file (video, audio, thumbnail) to Cloud Storage."""
        if not self.gcs_bucket:
            return None

        try:
            blob = self.gcs_bucket.blob(cloud_relative_path)
            blob.upload_from_filename(local_path)
            gcs_path = f"gs://{self.gcs_bucket.name}/{cloud_relative_path}"
            self.logger.info(f"Uploaded to Cloud Storage: {gcs_path}")
            return gcs_path
        except Exception as e:
            self.logger.warning(f"Failed to upload {cloud_relative_path} to Cloud Storage: {e}")
            return None

    def _log_to_firestore(self, result: Dict) -> None:
        """Log job completion to Firestore collection 'pipeline_runs'."""
        if not self.firestore_client:
            return

        try:
            collection = self.firestore_client.collection("pipeline_runs")
            doc_data = {
                "run_id": self.run_id,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "status": "success" if result.get("success") else "failure",
                "topic": result.get("topic", ""),
                "title": result.get("title", ""),
                "youtube_url": result.get("url", ""),
                "gcs_video_path": result.get("gcs_video_path", ""),
                "error_message": result.get("error") if not result.get("success") else None,
                "dry_run": self.dry_run,
                "provider": config.SCRIPT_MODEL_PROVIDER,
            }

            collection.document(self.run_id).set(doc_data)
            self.logger.info(f"Logged to Firestore: {self.run_id}")
        except Exception as e:
            self.logger.warning(f"Failed to log to Firestore: {e}")

    def _cleanup_old_outputs(self, max_age_days: int = 1, clear_cache_percent: float = 0.2) -> None:
        """Auto-cleanup old outputs and video cache after successful upload.

        Clears:
        - Output directories older than max_age_days
        - Video cache if it exceeds clear_cache_percent of disk usage
        """
        try:
            outputs_dir = Path("outputs")
            if not outputs_dir.exists():
                return

            now = time.time()
            deleted_size = 0
            deleted_dirs = []

            for item in outputs_dir.iterdir():
                if not item.is_dir() or item.name == "video_cache":
                    continue

                # Skip if directory is too new
                age_days = (now - item.stat().st_mtime) / 86400
                if age_days < max_age_days:
                    continue

                try:
                    size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                    shutil.rmtree(item)
                    deleted_size += size
                    deleted_dirs.append(f"{item.name} ({size/1024/1024:.1f}MB)")
                except Exception as e:
                    self.logger.warning(f"Failed to delete {item.name}: {e}")

            if deleted_dirs:
                self.logger.info(f"[CLEANUP] Deleted {len(deleted_dirs)} old output dirs: {', '.join(deleted_dirs)}")
                self.logger.info(f"[CLEANUP] Freed {deleted_size/1024/1024:.1f}MB")

            # Periodically clear video cache if disk usage is high
            cache_dir = outputs_dir / "video_cache"
            if cache_dir.exists():
                cache_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
                if cache_size > 2.5 * 1024 * 1024 * 1024:  # > 2.5GB
                    try:
                        shutil.rmtree(cache_dir)
                        cache_dir.mkdir(exist_ok=True)
                        self.logger.info(f"[CLEANUP] Cleared video cache ({cache_size/1024/1024/1024:.1f}GB)")
                    except Exception as e:
                        self.logger.warning(f"Failed to clear video cache: {e}")

        except Exception as e:
            self.logger.warning(f"Auto-cleanup failed: {e}")

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
    parser.add_argument("--mode", choices=["prefetch", "render", "auto", "shorts_from_existing"], default="auto",
                        help="prefetch=research+script+images only; render=pull queue+produce video; auto=full pipeline (default); shorts_from_existing=convert existing videos to Shorts")
    parser.add_argument("--pick_strategy", type=str, default="recent_high_views",
                        choices=["recent_high_views", "all_time_best", "underutilized", "manual"],
                        help="How to pick videos for Shorts conversion (shorts_from_existing mode only)")
    parser.add_argument("--batch", type=int, default=1,
                        help="Number of videos to convert in one run (shorts_from_existing mode)")
    args = parser.parse_args()

    # Show cost summary at start
    cost_tracker = GCPCostTracker(initial_credits=300.0)
    cost_tracker.print_summary()

    # Secrets are loaded in Orchestrator.__init__() via load_secrets_from_gcp()
    # This happens before agents are created, so APIs are available in Cloud Run
    orchestrator = Orchestrator(dry_run=args.dry_run)

    if args.mode == "prefetch":
        orchestrator.run_prefetch(count=args.count)
        results = []  # prefetch doesn't return results
    elif args.mode == "render":
        results = orchestrator.run_render(count=args.count)
    elif args.mode == "shorts_from_existing":
        results = orchestrator.run_shorts_from_existing(
            pick_strategy=args.pick_strategy,
            batch=args.batch
        )
    else:  # auto
        results = orchestrator.run(count=args.count, topic_override=args.topic)

    # Show final cost summary
    cost_tracker.print_summary()

    # Exit with error code if nothing succeeded
    if results and not any(r.get("success") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
