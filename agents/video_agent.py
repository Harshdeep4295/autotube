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

import hashlib
import json
import logging
import math
import os
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

from config import config

logger = logging.getLogger(__name__)

NICHE_COLORS = {
    "AI & Tech":        ((10, 10, 35),  (3, 3, 18),   (70, 130, 255)),
    "Finance":          ((8, 30, 8),    (3, 12, 3),   (40, 190, 70)),
    "Business":         ((28, 18, 8),   (12, 8, 3),   (240, 150, 25)),
    "Health":           ((32, 8, 8),    (12, 3, 3),   (240, 60, 60)),
    "History":          ((22, 18, 8),   (9, 7, 3),    (190, 140, 45)),
    "English Learning": ((8, 28, 18),   (3, 12, 8),   (40, 210, 120)),
    "default":          ((18, 8, 28),   (7, 3, 12),   (140, 70, 240)),
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

    # ── Public entry point ────────────────────────────────────────────────────

    def render(self, script: Dict, audio_path: str, output_path: str) -> str:
        from moviepy import AudioFileClip, CompositeVideoClip, ColorClip, ImageClip

        os.makedirs(Path(output_path).parent, exist_ok=True)

        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        sections = script.get("sections", [])
        visual_queries = script.get("visual_queries", [])
        hook_title_text = script.get("hook_title_text", script.get("title", "").upper()[:30])

        logger.info(f"Audio duration: {total_duration:.1f}s — rendering {len(sections)} sections")

        # 1. Fetch background media — V2: AI images (default) or V1: Pexels clips
        if config.VIDEO_BACKGROUND_MODE == "pexels":
            section_clip_paths = self._fetch_section_clips(sections, visual_queries)   # V1
        else:
            section_clip_paths = self._fetch_section_images(sections, visual_queries)  # V2

        # 1b. Assign a random animation effect to each section (no repeats within video)
        pool = list(self.animation_effects) if self.animation_effects else list(ANIMATION_EFFECTS)
        random.shuffle(pool)
        section_effects = [pool[i % len(pool)] for i in range(len(sections))]
        for i, eff in enumerate(section_effects):
            logger.info(f"Section {i+1} animation: {eff['name']}")

        # 2. Build background video (per-section footage stitched together)
        base_video = self._build_base_video(sections, section_clip_paths, total_duration, section_effects)

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
        all_clips = (
            [base_video, overlay]
            + ([hook_card] if hook_card else [])
            + section_title_clips
            + [watermark]
        )
        final = CompositeVideoClip(all_clips, size=(self.W, self.H))
        final = final.with_audio(audio)
        final = self._mix_background_music(final, total_duration)

        duration_min = total_duration / 60
        logger.info(f"Writing video: {output_path} (~{duration_min:.1f} min of footage, est. 5-8 min render)")
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
        logger.info(f"Video saved: {output_path}")
        self._save_used_clips()
        return output_path

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
        cinematic_fallbacks = [
            "cinematic aerial cityscape golden hour",
            "abstract technology neural network visualization",
            "futuristic data visualization dark background",
            "modern office skyline sunset",
            "artificial intelligence digital brain",
            "global network connections blue",
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

        if cache_path.exists() and cache_path.stat().st_size > 5_000:
            logger.info(f"AI image cache hit: {cache_path.name}")
            return str(cache_path)

        full_prompt = f"cinematic high quality {prompt}, 4K, professional photography, no text"
        encoded = urllib.parse.quote(full_prompt)
        seed = random.randint(1, 99999)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1920&height=1080&nologo=true&model=flux&seed={seed}"
        )

        max_retries = 3
        retry_delay = 2  # seconds, doubles on each retry

        for attempt in range(max_retries):
            try:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                with open(cache_path, "wb") as f:
                    f.write(resp.content)
                size_kb = cache_path.stat().st_size // 1024
                logger.info(f"AI image downloaded: {cache_path.name} ({size_kb}KB)")
                return str(cache_path)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    logger.info(f"Rate limited (429) — retrying in {retry_delay}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.warning(f"Pollinations image failed for '{prompt}': {e}")
                    if cache_path.exists():
                        cache_path.unlink()
                    return None
            except Exception as e:
                logger.warning(f"Pollinations image failed for '{prompt}': {e}")
                if cache_path.exists():
                    cache_path.unlink()
                return None

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

        n_frames = max(int(self.FPS * duration), 1)

        # Build per-frame expressions (replace N placeholder with actual frame count)
        def expr(s: str) -> str:
            return s.replace("N", str(n_frames))

        z_expr = expr(effect["z"])
        x_expr = expr(effect["x"])
        y_expr = expr(effect["y"])

        # Cache key: image path + effect name + duration
        cache_key = hashlib.md5(
            f"{img_path}|{effect['name']}|{duration:.2f}".encode()
        ).hexdigest()[:12]
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"fx_{cache_key}.mp4"

        if not (cache_path.exists() and cache_path.stat().st_size > 10_000):
            vf = (
                f"zoompan="
                f"z='{z_expr}':"
                f"x='{x_expr}':"
                f"y='{y_expr}':"
                f"d={n_frames}:"
                f"s={self.W}x{self.H}:"
                f"fps={self.FPS}"
            )
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
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.decode()[-400:])
                kb = cache_path.stat().st_size // 1024
                logger.info(f"FFmpeg effect '{effect['name']}': {cache_path.name} ({kb}KB)")
            except Exception as e:
                logger.warning(f"FFmpeg zoompan failed for effect '{effect['name']}': {e} — PIL fallback")
                return self._image_to_ken_burns_pil(img_path, duration)

        from moviepy import VideoFileClip
        return VideoFileClip(str(cache_path))

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

            if clip_path and clip_path.endswith(".jpg"):
                # V2: AI-generated image → animated effect clip via FFmpeg
                try:
                    clip = self._image_to_ken_burns_clip(clip_path, section_dur, effect=effect)
                    section_clips.append(clip)
                    t += section_dur
                    continue
                except Exception as e:
                    logger.warning(f"Section {i} animation failed ({e}) — using gradient")

            elif clip_path:
                # V1: Pexels video clip
                try:
                    raw = VideoFileClip(clip_path)
                    # Resize to fill 1920×1080 (crop to fit aspect ratio)
                    clip = self._resize_and_crop(raw, self.W, self.H)
                    # Loop if section is longer than clip
                    if clip.duration < section_dur:
                        loops = math.ceil(section_dur / clip.duration)
                        from moviepy import concatenate_videoclips as cv
                        clip = cv([clip] * loops, method="compose")
                    clip = clip.subclipped(0, section_dur)
                    section_clips.append(clip)
                    t += section_dur
                    continue
                except Exception as e:
                    logger.warning(f"Section {i} clip failed ({e}) — using gradient")

            # Gradient fallback for this section
            section_clips.append(self._gradient_clip(section_dur))
            t += section_dur

        if not section_clips:
            return self._gradient_video(total_duration)

        base = concatenate_videoclips(section_clips, method="compose")
        # Trim or pad to exact duration
        if base.duration > total_duration:
            base = base.subclipped(0, total_duration)
        elif base.duration < total_duration - 0.1:
            # Pad with last section's gradient
            pad = self._gradient_clip(total_duration - base.duration)
            base = concatenate_videoclips([base, pad], method="compose")

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
            return (
                ImageClip(np.array(img))
                .with_duration(duration)
                .with_position((32, 32))
                .with_opacity(0.85)
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
