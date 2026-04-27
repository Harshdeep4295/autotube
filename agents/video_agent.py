"""
Video Agent — Analytics Vidhya Style
Renders a 1920×1080 MP4 with:
  - 1 unique Pexels clip per script section (cinematic/beautiful footage)
  - Bold opening title card (hook text, large font, yellow accent)
  - YouTube-style caption pills at bottom (synced per section)
  - Small channel logo watermark — TOP LEFT
  - Thin accent progress bar at bottom edge
  - Optional background music mix

Visual reference: Analytics Vidhya Shorts style — cinematic footage unrelated to topic,
bold typography, clean captions, small tasteful branding top-left.

Fallback: if Pexels fails → animated gradient background + captions still work.
"""

import base64
import hashlib
import json
import logging
import math
import os
import random
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import psutil
import requests
from PIL import Image, ImageDraw, ImageFont

from agents.kling_video_agent import KlingVideoGenerator
from agents.imagen_agent import ImagenImageGenerator
from config import config

logger = logging.getLogger(__name__)

def _get_memory_status(label: str = ""):
    """Log current memory usage (RSS, available, percent). Helper for OOM debugging."""
    try:
        process = psutil.Process()
        rss_mb = process.memory_info().rss / (1024 * 1024)
        available_mb = psutil.virtual_memory().available / (1024 * 1024)
        percent = psutil.virtual_memory().percent
        logger.info(f"[MEMORY{f' {label}' if label else ''}] Process RSS: {rss_mb:.1f} MB | System available: {available_mb:.1f} MB | Usage: {percent:.1f}%")
    except Exception as e:
        logger.warning(f"[MEMORY] Failed to collect stats: {e}")

# Lazy import Veo if configured
try:
    from agents.gcp_veo_agent import VeoVideoGenerator
    VEO_AVAILABLE = True
except ImportError:
    VEO_AVAILABLE = False

NICHE_COLORS = {
    "AI & Tech":        ((10, 10, 35),  (3, 3, 18),   (70, 130, 255)),
    "Finance":          ((8, 30, 8),    (3, 12, 3),   (40, 190, 70)),
    "Business":         ((28, 18, 8),   (12, 8, 3),   (240, 150, 25)),
    "Health":           ((32, 8, 8),    (12, 3, 3),   (240, 60, 60)),
    "History":          ((22, 18, 8),   (9, 7, 3),    (190, 140, 45)),
    "English Learning": ((8, 28, 18),   (3, 12, 8),   (40, 210, 120)),
    "default":          ((18, 8, 28),   (7, 3, 12),   (140, 70, 240)),
}

# PHASE 1: Niche-specific color grading (saturation, brightness, contrast)
NICHE_COLOR_GRADES = {
    "AI & Tech":        {"saturation": 1.3, "brightness": 0.05, "contrast": 1.15},
    "Finance":          {"saturation": 1.2, "brightness": 0.1,  "contrast": 1.2},
    "Business":         {"saturation": 1.0, "brightness": 0.0,  "contrast": 1.25},
    "Health":           {"saturation": 1.1, "brightness": 0.08, "contrast": 1.1},
    "History":          {"saturation": 0.95,"brightness": 0.15, "contrast": 1.15},
    "English Learning": {"saturation": 1.15,"brightness": 0.08, "contrast": 1.15},
    "default":          {"saturation": 1.0, "brightness": 0.0,  "contrast": 1.1},
}

# Yellow accent for bold title cards (Analytics Vidhya style)
TITLE_CARD_ACCENT = (255, 210, 40)

# ── Animation effects — 17 FFmpeg zoompan presets ────────────────────────────
# Each effect is a dict with z/x/y zoompan expressions.
# "N" in any expression is replaced at runtime with the actual frame count.
# Loaded from Supabase `animation_effects` table if available; this is the fallback.
ANIMATION_EFFECTS = [
    # ── ZOOM (6) ──────────────────────────────────────────────────────────────
    {"name": "zoom_in",          "z": "min(1+0.15*on/N,1.15)", "x": "iw/2-(iw/zoom/2)",               "y": "ih/2-(ih/zoom/2)",              "weight": 2},
    {"name": "zoom_out",         "z": "max(1.15-0.15*on/N,1.0)","x": "iw/2-(iw/zoom/2)",              "y": "ih/2-(ih/zoom/2)",              "weight": 2},
    {"name": "zoom_in_tl",       "z": "min(1+0.15*on/N,1.15)", "x": "0",                              "y": "0",                             "weight": 1},
    {"name": "zoom_in_tr",       "z": "min(1+0.15*on/N,1.15)", "x": "iw-iw/zoom",                     "y": "0",                             "weight": 1},
    {"name": "zoom_in_bl",       "z": "min(1+0.15*on/N,1.15)", "x": "0",                              "y": "ih-ih/zoom",                    "weight": 1},
    {"name": "zoom_in_br",       "z": "min(1+0.15*on/N,1.15)", "x": "iw-iw/zoom",                     "y": "ih-ih/zoom",                    "weight": 1},
    # ── PAN (5) ───────────────────────────────────────────────────────────────
    {"name": "pan_right",        "z": "1.15",                  "x": "(on/N)*(iw-iw/zoom)",             "y": "ih/2-(ih/zoom/2)",              "weight": 2},
    {"name": "pan_left",         "z": "1.15",                  "x": "(1-on/N)*(iw-iw/zoom)",           "y": "ih/2-(ih/zoom/2)",              "weight": 2},
    {"name": "pan_up",           "z": "1.15",                  "x": "iw/2-(iw/zoom/2)",                "y": "(1-on/N)*(ih-ih/zoom)",         "weight": 1},
    {"name": "pan_down",         "z": "1.15",                  "x": "iw/2-(iw/zoom/2)",                "y": "(on/N)*(ih-ih/zoom)",           "weight": 1},
    {"name": "pan_slow_right",   "z": "1.08",                  "x": "(on/N)*(iw-iw/zoom)*0.5",         "y": "ih/2-(ih/zoom/2)",              "weight": 1},
    # ── DIAGONAL DRIFT (4) ────────────────────────────────────────────────────
    {"name": "drift_tr",         "z": "1.15",                  "x": "(on/N)*(iw-iw/zoom)*0.5",         "y": "(1-on/N)*(ih-ih/zoom)*0.5",    "weight": 1},
    {"name": "drift_bl",         "z": "1.15",                  "x": "(1-on/N)*(iw-iw/zoom)*0.5",       "y": "(on/N)*(ih-ih/zoom)*0.5",      "weight": 1},
    {"name": "drift_tl",         "z": "1.15",                  "x": "(1-on/N)*(iw-iw/zoom)*0.5",       "y": "(1-on/N)*(ih-ih/zoom)*0.5",   "weight": 1},
    {"name": "drift_br",         "z": "1.15",                  "x": "(on/N)*(iw-iw/zoom)*0.5",         "y": "(on/N)*(ih-ih/zoom)*0.5",     "weight": 1},
    # ── ZOOM + PAN COMBINED (2) ───────────────────────────────────────────────
    {"name": "zoom_in_drift_r",  "z": "min(1+0.12*on/N,1.12)", "x": "iw/2-(iw/zoom/2)+(on/N)*50",     "y": "ih/2-(ih/zoom/2)",              "weight": 1},
    {"name": "zoom_out_drift_l", "z": "max(1.12-0.12*on/N,1.0)","x": "iw/2-(iw/zoom/2)+(1-on/N)*50",  "y": "ih/2-(ih/zoom/2)",             "weight": 1},
    # ── PHASE 1: NEW MOTION EFFECTS (5) ────────────────────────────────────────
    {"name": "swing_pan",        "z": "1.15",                  "x": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.3*sin(2*PI*on/N)", "y": "ih/2-(ih/zoom/2)", "weight": 2},
    {"name": "spiral_zoom",      "z": "1+0.1*on/N",            "x": "iw/2-(iw/zoom/2)+(on/N)*(iw-iw/zoom)*0.3*cos(2*PI*on/N)", "y": "ih/2-(ih/zoom/2)+(on/N)*(ih-ih/zoom)*0.3*sin(2*PI*on/N)", "weight": 1},
    {"name": "reverse_zoom",     "z": "max(1.15-0.2*on/N,1.0)","x": "iw/2-(iw/zoom/2)",               "y": "ih/2-(ih/zoom/2)",              "weight": 1},
    {"name": "parallax",         "z": "1.08",                  "x": "iw/2-(iw/zoom/2)+(on/N)*(iw-iw/zoom)*0.15", "y": "ih/2-(ih/zoom/2)+(1-on/N)*(ih-ih/zoom)*0.1", "weight": 1},
    {"name": "drift_slow",       "z": "1.1",                   "x": "iw/2-(iw/zoom/2)+(on/N)*(iw-iw/zoom)*0.2*sin(PI*on/N)", "y": "ih/2-(ih/zoom/2)+(on/N)*(ih-ih/zoom)*0.15", "weight": 1},
]


class VideoAgent:
    """Renders 1920×1080 MP4 with per-section Pexels footage + caption overlays."""

    USED_CLIPS_FILE = "data/used_clips.json"

    def __init__(self):
        self.W = config.VIDEO_WIDTH
        self.H = config.VIDEO_HEIGHT
        self.FPS = config.VIDEO_FPS
        self.colors = NICHE_COLORS.get(config.CHANNEL_NICHE, NICHE_COLORS["default"])
        self.fonts = self._load_fonts()
        os.makedirs(config.VIDEO_CACHE_DIR, exist_ok=True)
        self._used_hashes: set = self._load_used_clips()
        self._new_hashes: set = set()   # hashes used in this run, saved after render
        self.animation_effects: List[Dict] = self._load_animation_effects()
        self.kling_generator = None
        self.veo_generator = None
        self.color_grade = NICHE_COLOR_GRADES.get(config.CHANNEL_NICHE, NICHE_COLOR_GRADES["default"])

    # ── Public entry point ────────────────────────────────────────────────────

    def render(self, script: Dict, audio_path: str, output_path: str, prefetched_images: Optional[Dict] = None) -> str:
        from moviepy import AudioFileClip, CompositeVideoClip, ColorClip, ImageClip

        os.makedirs(Path(output_path).parent, exist_ok=True)
        logger.info(f"[RENDER_START] ═══════════════════════════════════════")
        _get_memory_status("RENDER_START")

        audio_path = self._apply_audio_processing(audio_path)
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        sections = script.get("sections", [])
        visual_queries = script.get("visual_queries", [])
        hook_title_text = script.get("hook_title_text", script.get("title", "").upper()[:30])

        logger.info(f"Audio duration: {total_duration:.1f}s — rendering {len(sections)} sections")
        logger.info(f"Animation mode: {config.VIDEO_ANIMATION_MODE}")
        logger.info(f"Background mode: {config.VIDEO_BACKGROUND_MODE}")
        logger.info(f"Visual queries available: {len(visual_queries)} queries: {visual_queries}")
        logger.info(f"[PHASE 1] Color grading applied: {config.CHANNEL_NICHE} — {self.color_grade}")

        # Calculate section durations based on actual audio
        total_words = sum(len(s.get("text", "").split()) for s in sections)
        section_durations = {}
        for i, section in enumerate(sections):
            words = len(section.get("text", "").split())
            section_durations[i] = max(2.0, (words / max(total_words, 1)) * total_duration)
        logger.info(f"Section durations: {[f'{d:.1f}s' for d in section_durations.values()]}")

        # 1. Fetch background media — dispatch based on config + background mode + animation mode
        logger.info(f"[PHASE_1_FETCH] Fetching section videos...")
        _get_memory_status("BEFORE_FETCH")

        if prefetched_images is not None:
            section_clip_paths = prefetched_images
            logger.info(f"[RENDER] Using prefetched images from queue")
            for idx, path in prefetched_images.items():
                logger.info(f"  [PREFETCH] Section {idx}: {path}")
        elif config.VIDEO_BACKGROUND_MODE == "pexels":
            logger.info(f"[RENDER] Fetching Pexels clips (V1 mode)")
            section_clip_paths = self._fetch_section_clips(sections, visual_queries)   # V1: Pexels clips
        else:
            # V2: AI images with animation mode dispatch
            logger.info(f"[RENDER] Fetching section videos (V2 mode with {config.VIDEO_ANIMATION_MODE} animation)")
            section_clip_paths = self._get_section_videos(sections, visual_queries, section_durations)

        _get_memory_status("AFTER_FETCH")

        # 1b. Assign a random animation effect to each section (no repeats within video)
        pool = list(self.animation_effects) if self.animation_effects else list(ANIMATION_EFFECTS)
        random.shuffle(pool)
        section_effects = [pool[i % len(pool)] for i in range(len(sections))]
        for i, eff in enumerate(section_effects):
            logger.info(f"Section {i+1} animation: {eff['name']}")

        # 2. Build background video (per-section footage stitched together)
        logger.info(f"[PHASE_2_BUILD_BASE] Building base video with {len(sections)} sections...")
        _get_memory_status("BEFORE_BUILD_BASE")
        base_video = self._build_base_video(sections, section_clip_paths, total_duration, section_effects, visual_queries)
        _get_memory_status("AFTER_BUILD_BASE")

        # 3. Dark overlay for text contrast
        overlay = (
            ColorClip(size=(self.W, self.H), color=(0, 0, 0))
            .with_duration(total_duration)
            .with_opacity(config.DARK_OVERLAY_OPACITY)
        )

        # 4. Bold opening title card (shown first ~3.5s)
        hook_card = self._build_hook_title_card(hook_title_text, min(3.5, total_duration * 0.08))

        # 5. Section title cards — brief chapter heading at the start of each non-hook section
        section_title_clips = self._build_section_title_clips(sections, total_duration)

        # 6. Generate SRT captions file (uploaded to YouTube after publish — not burned in)
        self._generate_srt(sections, total_duration, str(Path(output_path).parent))

        # 7. Watermark — TOP LEFT
        watermark = self._make_watermark(total_duration)

        # 8. Composite all layers (no burned-in captions, no progress bar — YouTube provides its own)
        logger.info(f"[PHASE_3_COMPOSITE] Creating composite video with {len(section_title_clips)} title clips...")
        _get_memory_status("BEFORE_COMPOSITE")

        all_clips = (
            [base_video, overlay]
            + ([hook_card] if hook_card else [])
            + section_title_clips
            + [watermark]
        )
        logger.info(f"  Total clip layers: {len(all_clips)}")
        _get_memory_status("BEFORE_COMPOSITEvideoclip")

        final = CompositeVideoClip(all_clips, size=(self.W, self.H))
        logger.info(f"  ✓ CompositeVideoClip created")
        _get_memory_status("AFTER_COMPOSITEvideoclip")

        final = final.with_audio(audio)
        logger.info(f"  ✓ Audio attached")
        _get_memory_status("AFTER_AUDIO_ATTACH")

        final = self._mix_background_music(final, total_duration)
        logger.info(f"  ✓ Background music mixed")
        _get_memory_status("AFTER_MIX_MUSIC")

        duration_min = total_duration / 60
        logger.info(f"[PHASE_4_ENCODE] Writing video: {output_path} (~{duration_min:.1f} min of footage, est. 5-8 min render)")
        _get_memory_status("BEFORE_WRITE_VIDEOFILE")

        try:
            final.write_videofile(
                output_path,
                fps=self.FPS,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",   # 3-4x faster encode; file is larger but YouTube re-encodes anyway
                threads=2,            # match GitHub Actions vCPU count
                bitrate="4000k",      # ensure 720p+ quality source for YouTube
                temp_audiofile=str(Path(output_path).parent / "tmp_audio.aac"),
                remove_temp=True,
                logger="bar",         # show ffmpeg progress in logs
            )
        except MemoryError as e:
            logger.error(f"[OOM_DETECTED] MemoryError during write_videofile: {e}")
            _get_memory_status("OOM_DETECTED")
            raise
        except Exception as e:
            logger.error(f"[WRITE_VIDEOFILE_ERROR] {type(e).__name__}: {e}")
            _get_memory_status("ERROR_DURING_WRITE")
            raise

        logger.info(f"Video saved: {output_path}")
        _get_memory_status("AFTER_WRITE_VIDEOFILE")
        self._save_used_clips()
        return output_path

    # ── Per-scene fallback chain ─────────────────────────────────────────────

    def _get_section_videos(self, sections: List[Dict], visual_queries: List[str], section_durations: Dict[int, float] = None) -> Dict[int, Optional[str]]:
        """Generate videos for each section with per-scene fallback chain.
        Primary mode (from config) → LeiaPix → Ken Burns → Pexels → Gradient.
        On 429 rate limit, immediately switch to next mode for that scene.
        section_durations: dict mapping section index to required duration in seconds."""
        primary_mode = config.VIDEO_ANIMATION_MODE.lower()
        # Concrete, visualizable fallbacks for Veo (avoid abstractions)
        cinematic_fallbacks = [
            "drone camera flying over futuristic cityscape golden hour sunset",
            "robot hand assembling circuit board under bright white light",
            "holographic display showing 3D data visualization blue neon glow",
            "modern glass office building with warm sunset reflection",
            "android robot head with glowing blue eyes in dark background",
            "fiber optic cables with flowing blue light in dark space",
        ]

        results: Dict[int, Optional[str]] = {}
        for i, section in enumerate(sections):
            query = (
                visual_queries[i].strip()
                if i < len(visual_queries) and visual_queries[i].strip()
                else cinematic_fallbacks[i % len(cinematic_fallbacks)]
            )
            section_dur = section_durations.get(i, 8.0) if section_durations else 8.0
            video_path = self._try_section_video_chain(i, query, primary_mode, section_dur)
            results[i] = video_path
            status = f"'{video_path}'" if video_path else "gradient fallback"
            logger.info(f"Section {i+1}/{len(sections)} video: {status}")

        return results

    def _try_section_video_chain(self, section_idx: int, query: str, primary_mode: str, section_duration: float = 8.0) -> Optional[str]:
        """Try to generate a video for one section, falling back on errors.
        Veo test mode: ONLY Veo, no fallbacks (gradient only if Veo fails).
        section_duration: required video duration in seconds (passed to Veo to generate correctly-sized videos).
        """
        modes = []

        # Primary mode first, with intelligent fallbacks
        if primary_mode == "veo":
            # Veo primary, fall back to Ken Burns (free, reliable)
            modes = ["veo", "ken_burns"]
        elif primary_mode == "kling":
            modes = ["kling", "ken_burns", "pexels"]
        elif primary_mode == "seedance":
            modes = ["seedance", "ken_burns", "pexels"]
        elif primary_mode == "ken_burns":
            modes = ["ken_burns", "pexels"]
        elif primary_mode == "pika":
            modes = ["pika", "ken_burns", "pexels"]
        else:
            # Default fallback chain (seedance disabled — requires Replicate API key)
            modes = ["veo", "kling", "ken_burns", "pexels"]

        for mode in modes:
            try:
                if mode == "pika":
                    path = self._fetch_pika_video(query, section_idx)
                elif mode == "kling":
                    # Initialize generator if needed
                    if not self.kling_generator:
                        self.kling_generator = KlingVideoGenerator()

                    # Use asyncio to run async function (handle event loop properly)
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        path = loop.run_until_complete(
                            self.kling_generator.generate(query, section_idx)
                        )
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        path = loop.run_until_complete(
                            self.kling_generator.generate(query, section_idx)
                        )
                elif mode == "ken_burns":
                    img = self._fetch_ai_image(query, section_idx)
                    if img:
                        # _image_to_ken_burns_clip caches to disk automatically; we just need the cache key
                        effect = self.animation_effects[0] if self.animation_effects else ANIMATION_EFFECTS[0]
                        cache_key = hashlib.md5(
                            f"{img}|{effect['name']}|{5.0:.2f}".encode()
                        ).hexdigest()[:12]
                        path = str(Path(config.VIDEO_CACHE_DIR) / f"fx_{cache_key}.mp4")
                        # Ensure it was actually created by calling the method
                        try:
                            self._image_to_ken_burns_clip(img, 5.0, effect=effect)
                        except Exception:
                            path = None
                    else:
                        path = None
                elif mode == "pexels":
                    cinematic_fallbacks = [
                        "aerial cityscape drone",
                        "ocean waves cinematic",
                        "mountain landscape sunrise",
                        "forest path light",
                        "city night lights",
                        "abstract light motion",
                    ]
                    fb_query = cinematic_fallbacks[section_idx % len(cinematic_fallbacks)]
                    paths = self._fetch_pexels_clips(fb_query, n=1)
                    path = paths[0] if paths else None
                elif mode == "seedance":
                    path = self._fetch_seedance_video(query, section_idx)
                elif mode == "veo":
                    if not self.veo_generator:
                        self.veo_generator = VeoVideoGenerator()

                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        duration_int = min(int(round(section_duration)), 8)
                        path = loop.run_until_complete(
                            self.veo_generator.generate(query, section_idx, duration=duration_int)
                        )
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        duration_int = min(int(round(section_duration)), 8)
                        path = loop.run_until_complete(
                            self.veo_generator.generate(query, section_idx, duration=duration_int)
                        )
                else:
                    path = None

                if path:
                    logger.info(f"Section {section_idx+1}: {mode} succeeded")
                    return path

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logger.warning(f"Section {section_idx+1}: {mode} rate limited (429) → trying next mode")
                    continue
                else:
                    logger.warning(f"Section {section_idx+1}: {mode} failed ({e}) → trying next mode")
                    continue
            except Exception as e:
                logger.warning(f"Section {section_idx+1}: {mode} failed ({e}) → trying next mode")
                continue

        logger.warning(f"Section {section_idx+1}: all modes exhausted → gradient fallback")
        return None

    # ── Animation Mode 1: Pika (native video generation) ───────────────────────

    def _generate_videos_pika(self, sections: List[Dict], visual_queries: List[str]) -> Dict[int, Optional[str]]:
        """Generate videos using Pika API from visual_queries. Caches by prompt hash."""
        if not config.PIKA_API_KEY:
            logger.warning("Pika API key not set — falling back to ken_burns")
            return self._fetch_section_images(sections, visual_queries)

        # Concrete, visualizable fallbacks for Pika
        cinematic_fallbacks = [
            "drone flying over futuristic city at golden hour sunset",
            "robot hand assembling technological component bright light",
            "holographic 3D interface glowing blue in dark room",
            "modern glass skyscraper reflecting warm sunset light",
            "android robot head with glowing blue eyes dark background",
            "flowing blue neon light through fiber optic cables dark",
        ]

        results: Dict[int, Optional[str]] = {}
        for i, section in enumerate(sections):
            query = (
                visual_queries[i].strip()
                if i < len(visual_queries) and visual_queries[i].strip()
                else cinematic_fallbacks[i % len(cinematic_fallbacks)]
            )
            try:
                video_path = self._fetch_pika_video(query, i)
                results[i] = video_path
                status = f"'{video_path}'" if video_path else "gradient fallback"
                logger.info(f"Section {i+1}/{len(sections)} Pika video: {status}")
            except Exception as e:
                logger.warning(f"Section {i+1} Pika generation failed: {e} — gradient fallback")
                results[i] = None

        return results

    def _fetch_pika_video(self, prompt: str, section_idx: int) -> Optional[str]:
        """Request a video from Pika via fal.ai. Cached by prompt hash. Re-raises 429 for fallback chain.

        Pika is now officially hosted on fal.ai. Requires FAL_API_KEY from https://fal.ai
        """
        if not config.FAL_API_KEY:
            logger.warning("FAL_API_KEY not set — Pika mode unavailable (skipping to fallback)")
            raise ValueError("FAL_API_KEY not configured")

        import time
        prompt_hash = hashlib.md5(f"{prompt}_{section_idx}".encode()).hexdigest()[:12]
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"pika_{prompt_hash}.mp4"

        if cache_path.exists() and cache_path.stat().st_size > 100_000:
            logger.info(f"Pika video cache hit: {cache_path.name}")
            return str(cache_path)

        try:
            import requests
            import json as json_module

            full_prompt = f"cinematic high quality {prompt}, 4K, professional cinematography"

            # fal.ai endpoint for Pika text-to-video
            resp = requests.post(
                "https://api.fal.ai/v1/queue/text-to-video",
                headers={"Authorization": f"Key {config.FAL_API_KEY}"},
                json={
                    "prompt": full_prompt,
                    "duration": 5,
                    "aspect_ratio": "16:9",
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            # fal.ai returns data with 'video' field containing URL
            video_url = data.get("video", {}).get("url") if isinstance(data.get("video"), dict) else data.get("video")

            if not video_url:
                logger.warning(f"Pika/fal.ai API returned no video URL for '{prompt}'")
                return None

            # Download video
            video_resp = requests.get(video_url, timeout=120)
            video_resp.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(video_resp.content)
            size_mb = cache_path.stat().st_size / (1024 * 1024)
            logger.info(f"Pika video (via fal.ai) downloaded: {cache_path.name} ({size_mb:.1f}MB)")
            return str(cache_path)

        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 429:
                logger.warning(f"Pika/fal.ai rate limited (429) for '{prompt}' — re-raising for fallback chain")
                if cache_path.exists():
                    cache_path.unlink()
                raise  # Re-raise so fallback chain catches it
            else:
                logger.warning(f"Pika/fal.ai video generation failed for '{prompt}': {e}")
                if cache_path.exists():
                    cache_path.unlink()
                raise  # Re-raise HTTP errors
        except Exception as e:
            logger.warning(f"Pika/fal.ai video generation failed for '{prompt}': {e}")
            if cache_path.exists():
                cache_path.unlink()
            raise  # Re-raise all errors for fallback chain to handle

    def _fetch_seedance_video(self, prompt: str, section_idx: int) -> Optional[str]:
        """Fetch video from Seedance 2.0 via Replicate Python SDK. Free tier available.
        Requires REPLICATE_API_KEY from https://replicate.com/account"""
        if not config.REPLICATE_API_KEY:
            logger.warning("REPLICATE_API_KEY not set — Seedance unavailable (skipping to fallback)")
            raise ValueError("REPLICATE_API_KEY not configured")

        import os
        os.environ["REPLICATE_API_TOKEN"] = config.REPLICATE_API_KEY

        prompt_hash = hashlib.md5(f"{prompt}_{section_idx}".encode()).hexdigest()[:12]
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"seedance_{prompt_hash}.mp4"

        if cache_path.exists() and cache_path.stat().st_size > 100_000:
            logger.info(f"Seedance video cache hit: {cache_path.name}")
            return str(cache_path)

        try:
            import replicate
            import requests

            full_prompt = f"cinematic high quality {prompt}, 4K, professional cinematography"

            # Use Replicate Python SDK (handles auth, polling, everything)
            output = replicate.run(
                "bytedance/seedance-2.0",
                input={"prompt": full_prompt}
            )

            # Output is video URL
            if not output:
                logger.warning(f"Seedance returned no output for '{prompt}'")
                return None

            # Download video
            video_resp = requests.get(output, timeout=120)
            video_resp.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(video_resp.content)

            size_mb = cache_path.stat().st_size / (1024 * 1024)
            logger.info(f"Seedance video downloaded: {cache_path.name} ({size_mb:.1f}MB)")
            return str(cache_path)

        except Exception as e:
            logger.warning(f"Seedance video generation failed: {e}")
            return None

    # ── Animation Mode 2: LeiaPix (3D-depth animation from images) ──────────────

    def _animate_images_leiapix(self, sections: List[Dict], visual_queries: List[str]) -> Dict[int, Optional[str]]:
        """Fetch Pollinations images, then animate them with LeiaPix 3D-depth effect."""
        # First, fetch images like normal
        images = self._fetch_section_images(sections, visual_queries)

        # Then animate each image with LeiaPix
        results: Dict[int, Optional[str]] = {}
        for i, img_path in images.items():
            if not img_path:
                results[i] = None
                continue
            try:
                video_path = self._animate_leiapix_image(img_path, i)
                results[i] = video_path
                status = f"'{video_path}'" if video_path else "gradient fallback"
                logger.info(f"Section {i+1} LeiaPix animation: {status}")
            except Exception as e:
                logger.warning(f"Section {i+1} LeiaPix animation failed: {e} — gradient fallback")
                results[i] = None

        return results

    def _animate_leiapix_image(self, img_path: str, section_idx: int) -> Optional[str]:
        """Animate a static image using LeiaPix 3D-depth API (free, no key needed). Re-raises 429 for fallback."""
        import requests
        img_hash = hashlib.md5(f"{img_path}_{section_idx}".encode()).hexdigest()[:12]
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"leiapix_{img_hash}.mp4"

        if cache_path.exists() and cache_path.stat().st_size > 100_000:
            logger.info(f"LeiaPix cache hit: {cache_path.name}")
            return str(cache_path)

        try:
            # Upload image to LeiaPix API
            with open(img_path, "rb") as f:
                files = {"image": f}
                resp = requests.post(
                    "https://api.leiapix.com/api/v1/create",
                    files=files,
                    data={"duration": 5},
                    timeout=60,
                )
            resp.raise_for_status()
            data = resp.json()
            video_url = data.get("video_url")

            if not video_url:
                logger.warning(f"LeiaPix API returned no video URL")
                return None

            # Download video
            video_resp = requests.get(video_url, timeout=120)
            video_resp.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(video_resp.content)
            size_mb = cache_path.stat().st_size / (1024 * 1024)
            logger.info(f"LeiaPix video cached: {cache_path.name} ({size_mb:.1f}MB)")
            return str(cache_path)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"LeiaPix rate limited (429) — re-raising for fallback chain")
                if cache_path.exists():
                    cache_path.unlink()
                raise
            else:
                logger.warning(f"LeiaPix animation failed: {e}")
                if cache_path.exists():
                    cache_path.unlink()
                raise
        except Exception as e:
            logger.warning(f"LeiaPix animation failed: {e}")
            if cache_path.exists():
                cache_path.unlink()
            raise

    # ── Per-section Pexels clip fetching ─────────────────────────────────────

    def _fetch_section_clips(self, sections: List[Dict], visual_queries: List[str]) -> Dict[int, Optional[str]]:
        """Fetch one unique Pexels clip per section. Returns {section_idx: path_or_None}."""
        results: Dict[int, Optional[str]] = {}

        if not config.PEXELS_API_KEY:
            logger.info("No Pexels key — all sections will use gradient fallback")
            return {i: None for i in range(len(sections))}

        cinematic_fallbacks = [
            "aerial cityscape drone",
            "ocean waves cinematic",
            "mountain landscape sunrise",
            "forest path light",
            "city night lights",
            "abstract light motion",
        ]

        for i, section in enumerate(sections):
            # Use the visual_queries list if provided, else use cinematic fallbacks
            if i < len(visual_queries) and visual_queries[i].strip():
                query = visual_queries[i].strip()
            else:
                query = cinematic_fallbacks[i % len(cinematic_fallbacks)]

            paths = self._fetch_pexels_clips(query, n=1)
            if not paths:
                # Try a generic cinematic fallback
                fallback_q = cinematic_fallbacks[i % len(cinematic_fallbacks)]
                paths = self._fetch_pexels_clips(fallback_q, n=1)

            results[i] = paths[0] if paths else None
            status = f"'{results[i]}'" if results[i] else "gradient fallback"
            logger.info(f"Section {i + 1}/{len(sections)} clip for query='{query}': {status}")

        return results

    # ── V2: AI-generated images + Ken Burns ──────────────────────────────────

    def _fetch_section_images(self, sections: List[Dict], visual_queries: List[str]) -> Dict[int, Optional[str]]:
        """V2: Generate one Pollinations.ai image per section in parallel. Returns {idx: path_or_None}.
        Parallel fetch cuts download time from ~6-8 min (sequential) to ~1-2 min (concurrent).
        """
        # Concrete, visualizable fallbacks for Pollinations AI image generation
        cinematic_fallbacks = [
            "drone flying over futuristic cityscape golden hour sunset",
            "robot arm assembling circuit board bright white light",
            "holographic 3D display showing data blue neon glow",
            "modern glass office building sunset reflection",
            "android head glowing blue eyes dark background",
            "fiber optic cables blue light flowing dark space",
        ]

        def fetch_one(args):
            i, section = args
            query = (
                visual_queries[i].strip()
                if i < len(visual_queries) and visual_queries[i].strip()
                else cinematic_fallbacks[i % len(cinematic_fallbacks)]
            )
            path = self._fetch_ai_image(query, i)
            status = f"'{path}'" if path else "gradient fallback"
            logger.info(f"Section {i+1}/{len(sections)} image for query='{query}': {status}")
            return i, path

        results: Dict[int, Optional[str]] = {}
        # Limit to 2 concurrent requests to avoid Pollinations.ai rate limiting (429 errors)
        with ThreadPoolExecutor(max_workers=min(len(sections), 2)) as ex:
            futures = {ex.submit(fetch_one, (i, s)): i for i, s in enumerate(sections)}
            for future in as_completed(futures):
                try:
                    idx, path = future.result()
                    results[idx] = path
                except Exception as e:
                    idx = futures[future]
                    logger.warning(f"Section {idx+1} image fetch failed: {e}")
                    results[idx] = None
        return results

    def _fetch_ai_image(self, prompt: str, section_idx: int) -> Optional[str]:
        """
        Download a Pollinations.ai (Flux) image. Cached by prompt hash. No API key needed.
        Retries with exponential backoff on rate limit (429) errors.
        """
        import time
        import urllib.parse

        prompt_hash = hashlib.md5(f"{prompt}_{section_idx}".encode()).hexdigest()[:12]
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"{prompt_hash}.jpg"

        logger.info(f"    [_fetch_ai_image] Prompt: '{prompt}' | Hash: {prompt_hash}")

        if cache_path.exists() and cache_path.stat().st_size > 5_000:
            size_kb = cache_path.stat().st_size // 1024
            logger.info(f"    [_fetch_ai_image] ✓ CACHE HIT: {cache_path.name} ({size_kb}KB)")
            return str(cache_path)

        logger.info(f"    [_fetch_ai_image] Cache miss, trying image sources...")
        full_prompt = f"cinematic high quality {prompt}, 4K, professional photography, no text"

        # Try 1: Vertex AI Imagen (GCP native, no rate limits)
        logger.info(f"    [_fetch_ai_image] [1/2] Trying Vertex AI Imagen...")
        try:
            imagen = ImagenImageGenerator()
            image_b64 = imagen.generate(full_prompt, 1920, 1080)
            if image_b64:
                image_data = base64.b64decode(image_b64)
                with open(cache_path, "wb") as f:
                    f.write(image_data)
                size_kb = cache_path.stat().st_size // 1024
                logger.info(f"    [_fetch_ai_image] ✓ Imagen: {cache_path.name} ({size_kb}KB)")
                return str(cache_path)
        except Exception as e:
            logger.warning(f"    [_fetch_ai_image] Imagen failed: {e}")

        # Try 2: Pollinations.ai (fallback)
        logger.info(f"    [_fetch_ai_image] [2/2] Trying Pollinations.ai...")
        encoded = urllib.parse.quote(full_prompt)
        seed = random.randint(1, 99999)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1920&height=1080&nologo=true&model=flux&seed={seed}"
        )

        max_retries = 2
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"    [_fetch_ai_image] Attempt {attempt+1}/{max_retries}: GET request...")
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                with open(cache_path, "wb") as f:
                    f.write(resp.content)
                size_kb = cache_path.stat().st_size // 1024
                logger.info(f"    [_fetch_ai_image] ✓ Pollinations: {cache_path.name} ({size_kb}KB)")
                return str(cache_path)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    logger.warning(f"    [_fetch_ai_image] ⏳ Rate limited (429) — retrying in {retry_delay}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.warning(f"    [_fetch_ai_image] ✗ HTTP {e.response.status_code}: {e}")
                    if cache_path.exists():
                        cache_path.unlink()
                    return None
            except Exception as e:
                logger.warning(f"    [_fetch_ai_image] ✗ Exception: {type(e).__name__}: {e}")
                if cache_path.exists():
                    cache_path.unlink()
                return None

        logger.error(f"    [_fetch_ai_image] ✗ All retries exhausted")
        return None

    # ── Animation effects — DB-driven ─────────────────────────────────────────

    def _load_animation_effects(self) -> List[Dict]:
        """
        Load animation effects from Supabase `animation_effects` table (enabled=true, ordered by weight desc).
        Seeds the table with the 17 hardcoded effects on first run if it is empty.
        Falls back to ANIMATION_EFFECTS if Supabase is not configured or unavailable.
        """
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            logger.info("Supabase not configured — using hardcoded animation effects")
            return list(ANIMATION_EFFECTS)
        try:
            from supabase import create_client
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

            # Seed table if empty
            check = client.table("animation_effects").select("id").limit(1).execute()
            if not check.data:
                self._seed_effects_table(client)

            res = (
                client.table("animation_effects")
                .select("name,z_expr,x_expr,y_expr,weight")
                .eq("enabled", True)
                .order("weight", desc=True)
                .execute()
            )
            if res.data:
                # Normalize column names to match ANIMATION_EFFECTS keys (z/x/y)
                effects = [
                    {"name": r["name"], "z": r["z_expr"], "x": r["x_expr"],
                     "y": r["y_expr"], "weight": r.get("weight", 1)}
                    for r in res.data
                ]
                logger.info(f"Loaded {len(effects)} animation effects from Supabase")
                return effects
        except Exception as e:
            logger.warning(f"Failed to load animation effects from Supabase ({e}) — using hardcoded fallback")
        return list(ANIMATION_EFFECTS)

    def _seed_effects_table(self, client) -> None:
        """Insert the 17 hardcoded effects into Supabase on first run."""
        rows = [
            {
                "name":   eff["name"],
                "z_expr": eff["z"],
                "x_expr": eff["x"],
                "y_expr": eff["y"],
                "enabled": True,
                "weight":  eff.get("weight", 1),
            }
            for eff in ANIMATION_EFFECTS
        ]
        client.table("animation_effects").upsert(rows, on_conflict="name").execute()
        logger.info(f"Seeded animation_effects table with {len(rows)} effects")

    def _image_to_ken_burns_clip(self, img_path: str, duration: float, effect: Optional[Dict] = None):
        """
        Apply a named animation effect to a static image using FFmpeg zoompan (runs in C,
        ~20x faster than PIL per-frame). Generated clips are cached so repeat renders are instant.

        effect: dict with 'name', 'z', 'x', 'y' keys (from ANIMATION_EFFECTS / Supabase).
                "N" in any expression is replaced with the actual frame count at runtime.
        Falls back to PIL per-frame if FFmpeg fails.
        """
        if effect is None:
            effect = ANIMATION_EFFECTS[0]  # default: zoom_in

        logger.info(f"    [ken_burns] Image: {Path(img_path).name} | Duration: {duration:.1f}s | Effect: {effect['name']}")

        n_frames = max(int(self.FPS * duration), 1)

        # Build per-frame expressions (replace N placeholder with actual frame count)
        def expr(s: str) -> str:
            return s.replace("N", str(n_frames))

        z_expr = expr(effect["z"])
        x_expr = expr(effect["x"])
        y_expr = expr(effect["y"])

        logger.info(f"    [ken_burns] Frames: {n_frames} | FFmpeg filter: zoom={z_expr[:30]}...")

        # Cache key: image path + effect name + duration
        cache_key = hashlib.md5(
            f"{img_path}|{effect['name']}|{duration:.2f}".encode()
        ).hexdigest()[:12]
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"fx_{cache_key}.mp4"

        if cache_path.exists() and cache_path.stat().st_size > 10_000:
            kb = cache_path.stat().st_size // 1024
            logger.info(f"    [ken_burns] ✓ Cache hit: {cache_path.name} ({kb}KB)")
        else:
            logger.info(f"    [ken_burns] Cache miss, generating with FFmpeg...")
            vf = (
                f"zoompan="
                f"z='{z_expr}':"
                f"x='{x_expr}':"
                f"y='{y_expr}':"
                f"d={n_frames}:"
                f"s={self.W}x{self.H}:"
                f"fps={self.FPS}"
            )
            # PHASE 1B: Add color grading (niche-specific saturation, brightness, contrast)
            grade = self.color_grade
            vf += f",eq=saturation={grade['saturation']}:brightness={grade['brightness']}:contrast={grade['contrast']}"

            # PHASE 3A: Film grain + vignette (niche-conditional)
            if config.CHANNEL_NICHE in ("History", "Finance"):
                vf += ",noise=c0s=12:c1s=12:c2s=12:allf=t"
            vf += ",vignette=PI/4"

            # PHASE 3B: Chromatic aberration (AI & Tech only)
            if config.CHANNEL_NICHE == "AI & Tech":
                vf += ",rgbashift=rh=1:bh=-1"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", img_path,
                "-vf", vf,
                "-t", f"{duration:.3f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(cache_path),
            ]
            try:
                logger.info(f"    [ken_burns] Running FFmpeg command...")
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode != 0:
                    stderr_full = result.stderr.decode()
                    logger.error(f"    [ken_burns] FFmpeg stderr: {stderr_full[:200]}...")
                    raise RuntimeError(f"FFmpeg zoompan failed: {stderr_full}")
                kb = cache_path.stat().st_size // 1024
                logger.info(f"    [ken_burns] ✓ Generated: {cache_path.name} ({kb}KB)")
            except Exception as e:
                logger.warning(f"    [ken_burns] ✗ FFmpeg failed: {type(e).__name__}: {e}")
                logger.info(f"    [ken_burns] Falling back to PIL (slower)...")
                return self._image_to_ken_burns_pil(img_path, duration)

        logger.info(f"    [ken_burns] Loading video clip from cache...")
        from moviepy import VideoFileClip
        clip = VideoFileClip(str(cache_path))
        logger.info(f"    [ken_burns] ✓ Clip loaded, duration: {clip.duration:.1f}s")
        return clip

    def _image_to_ken_burns_pil(self, img_path: str, duration: float):
        """PIL per-frame fallback — only used if FFmpeg unavailable."""
        from moviepy import VideoClip
        img = Image.open(img_path).convert("RGB").resize((self.W, self.H), Image.LANCZOS)
        img_array = np.array(img)
        W, H = self.W, self.H

        def make_frame(t):
            progress = t / max(duration, 0.001)
            zoom = 1.0 + 0.12 * progress
            new_w, new_h = int(W * zoom), int(H * zoom)
            zoomed = np.array(Image.fromarray(img_array).resize((new_w, new_h), Image.BILINEAR))
            x1, y1 = (new_w - W) // 2, (new_h - H) // 2
            return zoomed[y1:y1 + H, x1:x1 + W]

        return VideoClip(make_frame, duration=duration)

    # ── Base video (per-section footage stitched) ─────────────────────────────

    def _build_base_video(
        self,
        sections: List[Dict],
        clip_paths: Dict[int, Optional[str]],
        total_duration: float,
        section_effects: Optional[List[Dict]] = None,
        visual_queries: Optional[List[str]] = None,
    ):
        from moviepy import VideoFileClip, concatenate_videoclips, ImageClip

        total_words = sum(len(s.get("text", "").split()) for s in sections)
        section_clips = []
        t = 0.0

        for i, section in enumerate(sections):
            words = len(section.get("text", "").split())
            section_dur = max(2.0, (words / max(total_words, 1)) * total_duration)
            clip_path = clip_paths.get(i)
            effect = section_effects[i] if section_effects and i < len(section_effects) else None
            # Get visual_query from the visual_queries list, fallback to empty
            visual_query = (visual_queries[i] if i < len(visual_queries) else "") if visual_queries else ""

            logger.info(f"\n[SECTION {i+1}/{len(sections)}] ─────────────────────────────────────")
            logger.info(f"  Duration: {section_dur:.1f}s | Words: {words} | Effect: {effect['name'] if effect else 'None'}")
            logger.info(f"  Clip path: {clip_path}")
            logger.info(f"  Visual query: '{visual_query}'")
            _get_memory_status(f"SECTION_{i+1}_START")

            if clip_path and clip_path.endswith(".jpg"):
                # V2: AI-generated image → animated effect clip via FFmpeg
                logger.info(f"  [JPG] AI image found, applying Ken Burns animation")
                try:
                    clip = self._image_to_ken_burns_clip(clip_path, section_dur, effect=effect)
                    section_clips.append(clip)
                    t += section_dur
                    logger.info(f"  ✓ [CLIP ADDED] Ken Burns animation successful")
                    continue
                except Exception as e:
                    logger.warning(f"  ✗ [KEN BURNS FAILED] Section {i} Ken Burns animation failed: {e}")

            elif clip_path and clip_path.endswith(".mp4"):
                # Prefetched cached video from prior job (may not exist due to cache isolation)
                logger.info(f"  [MP4] Checking if prefetch video exists...")
                if not Path(clip_path).exists():
                    logger.warning(f"  ✗ [PREFETCH MISS] Prefetch video not found: {clip_path}")
                    logger.info(f"  [FALLBACK] Attempting runtime video generation...")

                    # Try to regenerate Kling video at runtime if in kling mode
                    if config.VIDEO_ANIMATION_MODE == "kling":
                        logger.info(f"  [KLING] Mode is kling, attempting runtime generation with query: '{visual_query}'")
                        if visual_query:
                            try:
                                if not self.kling_generator:
                                    logger.info(f"  [KLING] Initializing KlingVideoGenerator...")
                                    self.kling_generator = KlingVideoGenerator()

                                logger.info(f"  [KLING] Starting async generation for: '{visual_query}'")
                                import asyncio
                                try:
                                    loop = asyncio.get_event_loop()
                                    if loop.is_closed():
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                    kling_path = loop.run_until_complete(
                                        self.kling_generator.generate(visual_query, i)
                                    )
                                except RuntimeError:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    kling_path = loop.run_until_complete(
                                        self.kling_generator.generate(visual_query, i)
                                    )

                                if kling_path and Path(kling_path).exists():
                                    logger.info(f"  ✓ [KLING SUCCESS] Video regenerated at runtime: {kling_path}")
                                    raw = VideoFileClip(kling_path)
                                    clip = self._resize_and_crop(raw, self.W, self.H)
                                    if clip.duration < section_dur:
                                        loops = math.ceil(section_dur / clip.duration)
                                        from moviepy import concatenate_videoclips as cv
                                        clip = cv([clip] * loops, method="chain")
                                    clip = clip.subclipped(0, section_dur)
                                    section_clips.append(clip)
                                    t += section_dur
                                    logger.info(f"  ✓ [CLIP ADDED] Kling video loaded and added to timeline")
                                    continue
                                else:
                                    logger.warning(f"  ✗ [KLING FAILED] Generated path does not exist: {kling_path}")
                            except Exception as e3:
                                logger.warning(f"  ✗ [KLING ERROR] Runtime Kling generation failed: {type(e3).__name__}: {e3}")
                                logger.info(f"  [FALLBACK] Falling back to Ken Burns...")
                        else:
                            logger.warning(f"  ✗ [KLING] No visual_query available, cannot attempt Kling generation")
                    else:
                        logger.info(f"  [FALLBACK] Not in kling mode (mode={config.VIDEO_ANIMATION_MODE}), skipping Kling generation")

                    # Fall back to Ken Burns if Kling not available or failed
                    logger.info(f"  [KEN BURNS] Attempting Ken Burns fallback...")
                    try:
                        # Concrete, visualizable fallbacks for Ken Burns AI image generation
                        cinematic_fallbacks = [
                            "drone flying over futuristic cityscape golden hour sunset",
                            "robot arm assembling circuit board bright white light",
                            "holographic 3D display showing data blue neon glow",
                            "modern glass office building sunset reflection",
                            "android head glowing blue eyes dark background",
                            "fiber optic cables blue light flowing dark space",
                        ]
                        query_to_use = visual_query if visual_query else cinematic_fallbacks[i % len(cinematic_fallbacks)]
                        logger.info(f"  [KEN BURNS] Fetching AI image with query: '{query_to_use}'")
                        img = self._fetch_ai_image(query_to_use, i)
                        if img:
                            logger.info(f"  [KEN BURNS] Image fetched: {img}, applying Ken Burns effect...")
                            clip = self._image_to_ken_burns_clip(img, section_dur, effect=effect)
                            section_clips.append(clip)
                            t += section_dur
                            logger.info(f"  ✓ [CLIP ADDED] Ken Burns fallback successful")
                            continue
                        else:
                            logger.warning(f"  ✗ [KEN BURNS] Failed to fetch AI image")
                    except Exception as e2:
                        logger.warning(f"  ✗ [KEN BURNS ERROR] Ken Burns regeneration failed: {type(e2).__name__}: {e2}")
                    # If all regeneration failed, fall through to gradient
                    logger.info(f"  [FALLBACK] All regeneration attempts failed, will use gradient fallback")
                else:
                    try:
                        logger.info(f"  [CACHED_MP4] Loading cached MP4 video...")
                        _get_memory_status(f"BEFORE_LOAD_CACHED_MP4_SECTION_{i+1}")
                        raw = VideoFileClip(clip_path)
                        logger.info(f"  [CACHED_MP4] Video loaded, duration: {raw.duration:.1f}s")
                        _get_memory_status(f"AFTER_LOAD_CACHED_MP4_SECTION_{i+1}")

                        clip = self._resize_and_crop(raw, self.W, self.H)
                        if clip.duration < section_dur:
                            loops = math.ceil(section_dur / clip.duration)
                            from moviepy import concatenate_videoclips as cv
                            clip = cv([clip] * loops, method="chain")
                        clip = clip.subclipped(0, section_dur)
                        section_clips.append(clip)
                        t += section_dur
                        _get_memory_status(f"AFTER_ADD_CACHED_MP4_SECTION_{i+1}")
                        logger.info(f"  ✓ [CLIP ADDED] Cached MP4 loaded and added")
                        continue
                    except Exception as e:
                        logger.warning(f"Section {i} cached video loading failed ({e}) — using gradient")
                        _get_memory_status(f"ERROR_LOAD_CACHED_MP4_SECTION_{i+1}")

            elif clip_path:
                # V1: Pexels video clip
                logger.info(f"  [PEXELS] Loading Pexels clip: {clip_path}")
                try:
                    _get_memory_status(f"BEFORE_LOAD_PEXELS_SECTION_{i+1}")
                    raw = VideoFileClip(clip_path)
                    logger.info(f"  [PEXELS] Video loaded, duration: {raw.duration:.1f}s, size: {raw.size}")
                    _get_memory_status(f"AFTER_LOAD_PEXELS_SECTION_{i+1}")

                    # Resize to fill 1920×1080 (crop to fit aspect ratio)
                    clip = self._resize_and_crop(raw, self.W, self.H)
                    # Loop if section is longer than clip
                    if clip.duration < section_dur:
                        loops = math.ceil(section_dur / clip.duration)
                        logger.info(f"  [PEXELS] Looping clip {loops}x to fill {section_dur:.1f}s duration")
                        from moviepy import concatenate_videoclips as cv
                        clip = cv([clip] * loops, method="chain")
                    clip = clip.subclipped(0, section_dur)
                    section_clips.append(clip)
                    t += section_dur
                    _get_memory_status(f"AFTER_ADD_PEXELS_SECTION_{i+1}")
                    logger.info(f"  ✓ [CLIP ADDED] Pexels clip loaded and added")
                    continue
                except Exception as e:
                    logger.warning(f"  ✗ [PEXELS ERROR] Section {i} clip failed: {type(e).__name__}: {e}")
                    logger.info(f"  [FALLBACK] Using gradient fallback for this section")
                    _get_memory_status(f"ERROR_LOAD_PEXELS_SECTION_{i+1}")

            # Gradient fallback for this section
            logger.warning(f"  [GRADIENT] Using solid gradient fallback for section {i}")
            section_clips.append(self._gradient_clip(section_dur))
            t += section_dur
            _get_memory_status(f"SECTION_{i+1}_END_GRADIENT_FALLBACK")

        if not section_clips:
            logger.error(f"[BUILD_BASE_VIDEO] No section clips available, using gradient fallback for entire video")
            return self._gradient_video(total_duration)

        logger.info(f"\n[BUILD_BASE_VIDEO] ═════════════════════════════════════════")
        logger.info(f"  Total sections: {len(section_clips)}")
        logger.info(f"  Target duration: {total_duration:.1f}s")
        _get_memory_status("BEFORE_ADD_TRANSITIONS")

        # PHASE 2C: Add dip-to-black transitions between sections
        logger.info(f"  Adding {len(section_clips) - 1} dip-to-black transitions...")
        clips_with_transitions = []
        for i, clip in enumerate(section_clips):
            clips_with_transitions.append(clip)
            if i < len(section_clips) - 1:
                clips_with_transitions.append(self._make_dip_to_black_transition(0.3))
        logger.info(f"  Total clips with transitions: {len(clips_with_transitions)}")
        _get_memory_status("BEFORE_CONCATENATE")

        logger.info(f"  Concatenating clips...")
        try:
            base = concatenate_videoclips(clips_with_transitions, method="chain")
            logger.info(f"  ✓ Concatenation successful")
        except MemoryError as e:
            logger.error(f"[OOM_IN_CONCATENATE] MemoryError during concatenate_videoclips: {e}")
            _get_memory_status("OOM_IN_CONCATENATE")
            raise
        except Exception as e:
            logger.error(f"[CONCATENATE_ERROR] {type(e).__name__}: {e}")
            _get_memory_status("ERROR_IN_CONCATENATE")
            raise

        _get_memory_status("AFTER_CONCATENATE")
        logger.info(f"  Concatenated duration: {base.duration:.1f}s")

        # Trim or pad to exact duration
        if base.duration > total_duration:
            logger.info(f"  [TRIM] Trimming {base.duration - total_duration:.1f}s excess")
            base = base.subclipped(0, total_duration)
        elif base.duration < total_duration - 0.1:
            # Pad with last section's gradient
            pad_duration = total_duration - base.duration
            logger.info(f"  [PAD] Adding {pad_duration:.1f}s gradient padding")
            pad = self._gradient_clip(pad_duration)
            base = concatenate_videoclips([base, pad], method="chain")

        logger.info(f"  Final duration: {base.duration:.1f}s ✓")
        return base

    def _resize_and_crop(self, clip, target_w: int, target_h: int):
        """Resize clip to fill target dimensions, cropping to maintain aspect ratio."""
        cw, ch = clip.size
        scale = max(target_w / cw, target_h / ch)
        new_w = int(cw * scale)
        new_h = int(ch * scale)
        resized = clip.resized(new_size=(new_w, new_h))
        # Crop to exact target size from center
        x1 = (new_w - target_w) // 2
        y1 = (new_h - target_h) // 2
        return resized.cropped(x1=x1, y1=y1, x2=x1 + target_w, y2=y1 + target_h)

    def _make_dip_to_black_transition(self, duration: float = 0.3):
        """PHASE 2C: Returns a black ColorClip for dip-to-black transitions between sections."""
        from moviepy import ColorClip
        return ColorClip(size=(self.W, self.H), color=(0, 0, 0)).with_duration(duration)

    def _gradient_clip(self, duration: float):
        """Single gradient ImageClip for the given duration."""
        from moviepy import ImageClip
        bg_start, bg_end, accent = self.colors
        img = Image.new("RGB", (self.W, self.H))
        draw = ImageDraw.Draw(img)
        for y in range(self.H):
            t = y / self.H
            r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * t)
            g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * t)
            b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * t)
            draw.line([(0, y), (self.W, y)], fill=(r, g, b))
        # Subtle grid lines for depth
        for x in range(0, self.W, 80):
            draw.line([(x, 0), (x, self.H)], fill=(255, 255, 255, 8))
        return ImageClip(np.array(img)).with_duration(duration)

    def _gradient_video(self, duration: float):
        """Full animated gradient video fallback."""
        from moviepy import concatenate_videoclips
        clip = self._gradient_clip(min(duration, 5.0))
        loops = math.ceil(duration / clip.duration)
        base = concatenate_videoclips([clip] * loops, method="compose")
        return base.subclipped(0, duration)

    # ── Pexels video download ─────────────────────────────────────────────────

    def _fetch_pexels_clips(self, query: str, n: int = 1) -> List[str]:
        """Download up to n HD clips from Pexels, cache them locally.
        Uses a random page each call so results vary across runs."""
        headers = {"Authorization": config.PEXELS_API_KEY}
        params = {
            "query": query,
            "orientation": "landscape",
            "size": "large",
            "per_page": 15,
            "page": random.randint(1, 8),   # random page → different pool each run
            "min_duration": 5,
            "max_duration": 15,
        }
        try:
            r = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params,
                timeout=15,
            )
            r.raise_for_status()
            videos = r.json().get("videos", [])
        except Exception as e:
            logger.warning(f"Pexels API request failed for '{query}': {e}")
            return []

        downloaded = []
        random.shuffle(videos)
        for video in videos:
            if len(downloaded) >= n:
                break
            path = self._download_clip(video)
            if path:
                downloaded.append(path)

        return downloaded

    def _download_clip(self, video: Dict) -> Optional[str]:
        """Download the best HD file from a Pexels video dict. Returns local path."""
        video_files = video.get("video_files", [])
        hd_files = [
            f for f in video_files
            if f.get("quality") in ("hd", "uhd")
            and f.get("width", 0) >= 1280
            and f.get("file_type") == "video/mp4"
        ]
        if not hd_files:
            hd_files = [f for f in video_files if f.get("file_type") == "video/mp4"]
        if not hd_files:
            return None

        best = max(hd_files, key=lambda f: f.get("width", 0))
        url = best.get("link", "")
        if not url:
            return None

        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]

        # Skip clips already used in a previous video
        if url_hash in self._used_hashes:
            return None

        cache_path = Path(config.VIDEO_CACHE_DIR) / f"{url_hash}.mp4"
        if cache_path.exists() and cache_path.stat().st_size > 10_000:
            self._new_hashes.add(url_hash)
            return str(cache_path)

        try:
            with requests.get(url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(cache_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 512):
                        f.write(chunk)
            self._new_hashes.add(url_hash)
            logger.info(f"Downloaded clip: {cache_path.name} ({cache_path.stat().st_size // 1024}KB)")
            return str(cache_path)
        except Exception as e:
            logger.warning(f"Clip download failed: {e}")
            if cache_path.exists():
                cache_path.unlink()
            return None

    # ── Used-clips tracking (prevent cross-video repetition) ─────────────────

    def _load_used_clips(self) -> set:
        """Load set of previously used clip hashes from disk."""
        try:
            with open(self.USED_CLIPS_FILE) as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _save_used_clips(self) -> None:
        """Persist all used clip hashes (old + new) so future runs skip them."""
        os.makedirs("data", exist_ok=True)
        all_hashes = list(self._used_hashes | self._new_hashes)
        with open(self.USED_CLIPS_FILE, "w") as f:
            json.dump(all_hashes, f)
        self._used_hashes = set(all_hashes)
        logger.info(f"Used-clips registry: {len(all_hashes)} total hashes saved")

    # ── Hook title card (bold opener) ─────────────────────────────────────────

    def _build_hook_title_card(self, text: str, duration: float):
        """Bold large title card shown at video start — Analytics Vidhya style."""
        from moviepy import ImageClip
        try:
            img = self._render_hook_card_image(text)
            return (
                ImageClip(np.array(img))
                .with_duration(duration)
                .with_start(0)
                .with_position("center")
            )
        except Exception as e:
            logger.warning(f"Hook title card failed: {e}")
            return None

    def _render_hook_card_image(self, text: str) -> Image.Image:
        """Render a full-frame hook title card with dot-matrix bg and yellow accent."""
        _, _, accent = self.colors
        canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        # Semi-transparent dark overlay (0.88 opacity)
        draw.rectangle([0, 0, self.W, self.H], fill=(0, 0, 0, 224))

        # Subtle dot matrix pattern for depth
        for x in range(0, self.W, 28):
            for y in range(0, self.H, 28):
                draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 18))

        # Accent bar on left edge
        draw.rectangle([0, 0, 6, self.H], fill=(*TITLE_CARD_ACCENT, 200))

        # Split text to make 1-2 key words yellow (last word gets accent)
        words = text.split()
        if len(words) >= 2:
            main_words = words[:-1]
            accent_words = words[-1:]
        else:
            main_words = words
            accent_words = []

        main_text = " ".join(main_words)
        accent_text = " ".join(accent_words)

        font_big = self.fonts["hook"]
        font_accent = self.fonts["hook"]

        # Measure combined width to center
        d_temp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        w_main = d_temp.textbbox((0, 0), main_text + " ", font=font_big)[2] if main_text else 0
        w_accent = d_temp.textbbox((0, 0), accent_text, font=font_accent)[2] if accent_text else 0
        total_w = w_main + w_accent

        start_x = (self.W - total_w) // 2
        y = self.H // 2 - 70  # slightly above center

        # Drop shadow
        if main_text:
            draw.text((start_x + 3, y + 3), main_text + (" " if accent_text else ""),
                      font=font_big, fill=(0, 0, 0, 180))
        if accent_text:
            draw.text((start_x + w_main + 3, y + 3), accent_text,
                      font=font_accent, fill=(0, 0, 0, 180))

        # White main text
        if main_text:
            draw.text((start_x, y), main_text + (" " if accent_text else ""),
                      font=font_big, fill=(255, 255, 255, 255))
        # Yellow accent word
        if accent_text:
            draw.text((start_x + w_main, y), accent_text,
                      font=font_accent, fill=(*TITLE_CARD_ACCENT, 255))

        # Thin accent underline
        line_y = y + 95
        draw.rectangle([start_x, line_y, start_x + total_w, line_y + 4],
                        fill=(*TITLE_CARD_ACCENT, 200))

        return canvas

    # ── Section title cards ───────────────────────────────────────────────────

    def _build_section_title_clips(self, sections: List[Dict], total_duration: float) -> List:
        """
        Shows a brief 2.5s chapter title card at the start of each non-hook/non-cta section.
        Uses section_display_title from the script if available, else skips.
        Positioned upper-center so it doesn't clash with watermark (top-left).
        """
        from moviepy import ImageClip

        total_chars = sum(len(s.get("text", "")) for s in sections)
        clips = []
        t = 0.0
        CARD_DURATION = 2.5  # seconds the title card is visible

        for section in sections:
            text = section.get("text", "").strip()
            section_chars = len(text)
            section_dur = max(2.0, (section_chars / max(total_chars, 1)) * total_duration)

            display_title = section.get("section_display_title", "").strip()
            name = section.get("section_name", "")

            # Show title card for context and main sections only (skip hook & cta)
            if display_title and name not in ("hook", "cta"):
                try:
                    img = self._render_section_title_image(display_title)
                    clip = (
                        ImageClip(np.array(img))
                        .with_duration(min(CARD_DURATION, section_dur * 0.4))
                        .with_start(t)
                        .with_position(("center", 140))  # upper area, below watermark zone
                        .with_opacity(lambda time: min(1.0, time / 0.4) if time < 0.4 else 1.0)  # PHASE 2A: fade-in
                    )
                    clips.append(clip)
                except Exception as e:
                    logger.warning(f"Section title card failed for '{display_title}': {e}")

            t += section_dur

        return clips

    def _render_section_title_image(self, text: str) -> Image.Image:
        """Renders a minimal chapter title — small accent bar + bold text, upper center."""
        _, _, accent = self.colors
        font = self.fonts["section_title"]

        dummy = Image.new("RGBA", (1, 1))
        d = ImageDraw.Draw(dummy)
        bbox = d.textbbox((0, 0), text.upper(), font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x, pad_y = 48, 20
        bar_h = 4
        img_w = tw + pad_x * 2
        img_h = th + pad_y * 2 + bar_h + 8

        canvas = Image.new("RGBA", (self.W, img_h + 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        x0 = (self.W - img_w) // 2
        y0 = 10

        # Semi-transparent dark pill
        draw.rounded_rectangle([x0, y0, x0 + img_w, y0 + img_h], radius=10, fill=(0, 0, 0, 160))

        # Accent bar on left inside pill
        draw.rectangle([x0, y0, x0 + bar_h + 4, y0 + img_h], fill=(*accent, 220))

        # Bold white text centered in pill
        tx = self.W // 2
        ty = y0 + pad_y + th // 2
        draw.text((tx, ty), text.upper(), font=font, fill=(255, 255, 255, 240), anchor="mm")

        return canvas

    # ── Caption clips ─────────────────────────────────────────────────────────

    def _build_caption_clips(self, sections: List[Dict], total_duration: float) -> List:
        """Build subtitle-style ImageClips for each section, bottom-center."""
        from moviepy import ImageClip

        total_words = sum(len(s.get("text", "").split()) for s in sections)
        clips = []
        t = 0.0

        for section in sections:
            text = section.get("text", "").strip()
            if not text:
                continue
            words = text.split()
            section_words = len(words)
            section_dur = max(2.0, (section_words / max(total_words, 1)) * total_duration)

            chunk_size = config.CAPTION_WORDS_PER_LINE * 2
            chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
            chunk_dur = section_dur / max(len(chunks), 1)

            for chunk in chunks:
                img = self._render_caption_image(chunk)
                clip = (
                    ImageClip(np.array(img))
                    .with_duration(chunk_dur)
                    .with_start(t)
                    .with_position(("center", self.H - 180))
                )
                clips.append(clip)
                t += chunk_dur

        return clips

    def _render_caption_image(self, words: List[str]) -> Image.Image:
        """Render a subtitle-style caption image (dark pill, white text)."""
        cpw = config.CAPTION_WORDS_PER_LINE
        line1_words = words[:cpw]
        line2_words = words[cpw:cpw * 2]
        line1 = " ".join(line1_words)
        line2 = " ".join(line2_words) if line2_words else ""

        font = self.fonts["caption"]
        dummy = Image.new("RGBA", (1, 1))
        d = ImageDraw.Draw(dummy)
        w1 = d.textbbox((0, 0), line1, font=font)[2]
        w2 = d.textbbox((0, 0), line2, font=font)[2] if line2 else 0
        text_w = max(w1, w2, 100)
        lines = 2 if line2 else 1
        text_h = lines * (config.CAPTION_FONT_SIZE + 10)

        pad_x, pad_y = 40, 20
        pill_w = text_w + pad_x * 2
        pill_h = text_h + pad_y * 2

        canvas = Image.new("RGBA", (self.W, pill_h + 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        x0 = (self.W - pill_w) // 2
        y0 = 10
        x1 = x0 + pill_w
        y1 = y0 + pill_h
        draw.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=(0, 0, 0, 190))

        ty = y0 + pad_y
        draw.text((self.W // 2, ty), line1, font=font, fill=(255, 255, 255, 255), anchor="mt")
        if line2:
            draw.text((self.W // 2, ty + config.CAPTION_FONT_SIZE + 8), line2,
                      font=font, fill=(255, 255, 255, 230), anchor="mt")

        return canvas

    # ── SRT caption file generation ───────────────────────────────────────────

    def _generate_srt(self, sections: List[Dict], total_duration: float, output_dir: str) -> Optional[str]:
        """
        Generate an SRT subtitle file synced to audio timing.
        Uses CHARACTER COUNT (not word count) for section duration proportioning —
        character count matches TTS phoneme density much more accurately than word count,
        which fixes the "subtitles running ahead of audio" problem.
        Each chunk also gets a small trailing gap (0.15s) so text clears before next line.
        """
        # Character count proportioning — more accurate than word count for TTS sync
        total_chars = sum(len(s.get("text", "")) for s in sections)
        entries = []
        t = 0.0
        idx = 1
        TRAILING_GAP = 0.15  # seconds of silence after each caption before next one starts

        for section in sections:
            text = section.get("text", "").strip()
            if not text:
                continue
            words = text.split()
            section_chars = len(text)
            # Proportion by characters, not words — accounts for long vs short words in TTS
            section_dur = max(2.0, (section_chars / max(total_chars, 1)) * total_duration)

            chunk_size = config.CAPTION_WORDS_PER_LINE * 2
            chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]

            # Distribute section duration proportionally by chunk character count too
            chunk_chars = [len(" ".join(c)) for c in chunks]
            total_chunk_chars = max(sum(chunk_chars), 1)

            for i, chunk in enumerate(chunks):
                chunk_dur = (chunk_chars[i] / total_chunk_chars) * section_dur
                display_dur = max(0.5, chunk_dur - TRAILING_GAP)

                start_str = self._seconds_to_srt_timestamp(t)
                end_str = self._seconds_to_srt_timestamp(t + display_dur)

                cpw = config.CAPTION_WORDS_PER_LINE
                line1 = " ".join(chunk[:cpw])
                line2 = " ".join(chunk[cpw:]) if len(chunk) > cpw else ""
                caption_text = f"{line1}\n{line2}" if line2 else line1

                entries.append(f"{idx}\n{start_str} --> {end_str}\n{caption_text}")
                idx += 1
                t += chunk_dur  # advance by full chunk_dur (including gap)

        srt_path = str(Path(output_dir) / "captions.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(entries) + "\n")

        logger.info(f"Generated SRT: {srt_path} ({len(entries)} entries)")
        return srt_path

    @staticmethod
    def _seconds_to_srt_timestamp(seconds: float) -> str:
        """Convert float seconds to SRT timestamp format HH:MM:SS,mmm."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    # ── Progress bar ──────────────────────────────────────────────────────────

    # ── Watermark — TOP LEFT ──────────────────────────────────────────────────

    def _make_watermark(self, duration: float):
        """Small channel logo watermark positioned top-left (Analytics Vidhya style)."""
        from moviepy import ImageClip
        try:
            _, _, accent = self.colors
            font = self.fonts["label"]
            dummy = Image.new("RGBA", (1, 1))
            d = ImageDraw.Draw(dummy)
            bbox = d.textbbox((0, 0), config.CHANNEL_NAME, font=font)
            tw = bbox[2] - bbox[0]

            icon_r = 10
            icon_diam = icon_r * 2
            spacing = 10
            total_w = icon_diam + spacing + tw + 24
            img_h = 40

            img = Image.new("RGBA", (total_w, img_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Semi-transparent dark background pill
            draw.rounded_rectangle([0, 0, total_w, img_h], radius=8, fill=(0, 0, 0, 110))

            # Accent circle icon (like a channel logo placeholder)
            cx = 12 + icon_r
            cy = img_h // 2
            draw.ellipse(
                [cx - icon_r, cy - icon_r, cx + icon_r, cy + icon_r],
                fill=(*accent, 230),
            )

            # Channel name text — anchor="lm" centers vertically at circle midpoint
            tx = 12 + icon_diam + spacing
            draw.text((tx, cy), config.CHANNEL_NAME,
                      font=font, fill=(255, 255, 255, 200), anchor="lm")

            # Position: top-left at (32, 32)
            # PHASE 2B: Animated watermark (fade-in, then stable)
            return (
                ImageClip(np.array(img))
                .with_duration(duration)
                .with_position((32, 32))
                .with_opacity(lambda t: min(0.85, t / 1.0) if t < 1.0 else 0.85)  # fade in over 1s, then hold
            )
        except Exception as e:
            logger.warning(f"Watermark failed: {e}")
            from moviepy import ColorClip
            return ColorClip(size=(1, 1), color=(0, 0, 0)).with_duration(duration).with_opacity(0)

    # ── Background music ──────────────────────────────────────────────────────

    def _mix_background_music(self, video, duration: float):
        from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
        from moviepy.audio.fx import MultiplyVolume

        # Respect MUSIC_ENABLED flag — YouTube deducts 55% earnings for licensed music
        if not config.MUSIC_ENABLED:
            logger.info("Background music disabled (MUSIC_ENABLED=false)")
            return video

        music_dir = Path(config.MUSIC_DIR)
        music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
        if not music_files:
            return video
        try:
            music = AudioFileClip(str(random.choice(music_files)))
            if music.duration < duration:
                loops = math.ceil(duration / music.duration)
                music = concatenate_audioclips([music] * loops)
            music = music.subclipped(0, duration).with_effects([MultiplyVolume(0.06)])
            combined = CompositeAudioClip([video.audio, music]) if video.audio else music
            return video.with_audio(combined)
        except Exception as e:
            logger.warning(f"Background music mixing failed (skipping): {e}")
            return video

    # ── PHASE 1C: Audio EQ + Compression ──────────────────────────────────────

    def _apply_audio_processing(self, audio_path: str) -> str:
        """FFmpeg: voice EQ (boost 2-4kHz presence, cut rumble below 100Hz) + compression.
        Returns original path if FFmpeg fails — full fallback."""
        try:
            out = str(Path(audio_path).parent / "audio_eq.mp3")
            cmd = [
                "ffmpeg", "-y", "-i", audio_path,
                "-af", (
                    "equalizer=f=100:t=h:width=1:g=-4,"
                    "equalizer=f=3000:t=p:width=100:g=3,"
                    "acompressor=threshold=-20:ratio=4:attack=50:release=200:makeup=2"
                ),
                "-acodec", "mp3", "-b:a", "192k", out
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                logger.info("[PHASE 1C] Audio EQ + compression applied successfully")
                return out
            else:
                logger.warning(f"[PHASE 1C] Audio EQ failed: {result.stderr.decode()[:200]}")
                return audio_path
        except Exception as e:
            logger.warning(f"[PHASE 1C] Audio processing skipped: {e}")
            return audio_path

    # ── Font loading ──────────────────────────────────────────────────────────

    def _load_fonts(self) -> Dict:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]

        def load(size: int) -> ImageFont.ImageFont:
            for p in candidates:
                try:
                    return ImageFont.truetype(p, size)
                except (IOError, OSError):
                    pass
            return ImageFont.load_default()

        return {
            "hook":          load(96),   # large bold title card text
            "section_title": load(48),   # chapter heading cards
            "caption":       load(config.CAPTION_FONT_SIZE),
            "label":         load(26),
        }
