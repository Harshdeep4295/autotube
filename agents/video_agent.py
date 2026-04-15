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
import logging
import math
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

from config import config

logger = logging.getLogger(__name__)

NICHE_COLORS = {
    "AI & Tech":  ((10, 10, 35),  (3, 3, 18),   (70, 130, 255)),
    "Finance":    ((8, 30, 8),    (3, 12, 3),   (40, 190, 70)),
    "Business":   ((28, 18, 8),   (12, 8, 3),   (240, 150, 25)),
    "Health":     ((32, 8, 8),    (12, 3, 3),   (240, 60, 60)),
    "History":    ((22, 18, 8),   (9, 7, 3),    (190, 140, 45)),
    "default":    ((18, 8, 28),   (7, 3, 12),   (140, 70, 240)),
}

# Yellow accent for bold title cards (Analytics Vidhya style)
TITLE_CARD_ACCENT = (255, 210, 40)


class VideoAgent:
    """Renders 1920×1080 MP4 with per-section Pexels footage + caption overlays."""

    def __init__(self):
        self.W = config.VIDEO_WIDTH
        self.H = config.VIDEO_HEIGHT
        self.FPS = config.VIDEO_FPS
        self.colors = NICHE_COLORS.get(config.CHANNEL_NICHE, NICHE_COLORS["default"])
        self.fonts = self._load_fonts()
        os.makedirs(config.VIDEO_CACHE_DIR, exist_ok=True)

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

        # 1. Fetch one unique Pexels clip per section
        section_clip_paths = self._fetch_section_clips(sections, visual_queries)

        # 2. Build background video (per-section footage stitched together)
        base_video = self._build_base_video(sections, section_clip_paths, total_duration)

        # 3. Dark overlay for text contrast
        overlay = (
            ColorClip(size=(self.W, self.H), color=(0, 0, 0))
            .with_duration(total_duration)
            .with_opacity(config.DARK_OVERLAY_OPACITY)
        )

        # 4. Bold opening title card (shown first ~3.5s)
        hook_card = self._build_hook_title_card(hook_title_text, min(3.5, total_duration * 0.08))

        # 5. Caption clips (subtitle style, synced per section)
        caption_clips = self._build_caption_clips(sections, total_duration)

        # 6. Progress bar
        progress_clips = self._build_progress_clips(sections, total_duration)

        # 7. Watermark — TOP LEFT
        watermark = self._make_watermark(total_duration)

        # 8. Composite all layers
        all_clips = (
            [base_video, overlay]
            + ([hook_card] if hook_card else [])
            + caption_clips
            + progress_clips
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
            temp_audiofile=str(Path(output_path).parent / "tmp_audio.aac"),
            remove_temp=True,
            logger="bar",         # show ffmpeg progress in logs
        )
        logger.info(f"Video saved: {output_path}")
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

    # ── Base video (per-section footage stitched) ─────────────────────────────

    def _build_base_video(
        self,
        sections: List[Dict],
        clip_paths: Dict[int, Optional[str]],
        total_duration: float,
    ):
        from moviepy import VideoFileClip, concatenate_videoclips, ImageClip

        total_words = sum(len(s.get("text", "").split()) for s in sections)
        section_clips = []
        t = 0.0

        for i, section in enumerate(sections):
            words = len(section.get("text", "").split())
            section_dur = max(2.0, (words / max(total_words, 1)) * total_duration)
            clip_path = clip_paths.get(i)

            if clip_path:
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
        """Download up to n HD clips from Pexels, cache them locally."""
        headers = {"Authorization": config.PEXELS_API_KEY}
        params = {
            "query": query,
            "orientation": "landscape",
            "size": "large",
            "per_page": 15,
            "min_duration": 5,
            "max_duration": 40,
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
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"{url_hash}.mp4"
        if cache_path.exists() and cache_path.stat().st_size > 10_000:
            return str(cache_path)

        try:
            with requests.get(url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(cache_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 512):
                        f.write(chunk)
            logger.info(f"Cached clip: {cache_path.name} ({cache_path.stat().st_size // 1024}KB)")
            return str(cache_path)
        except Exception as e:
            logger.warning(f"Clip download failed: {e}")
            if cache_path.exists():
                cache_path.unlink()
            return None

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

    # ── Progress bar ──────────────────────────────────────────────────────────

    def _build_progress_clips(self, sections: List[Dict], total_duration: float) -> List:
        """Thin accent-colored progress bar at very bottom of screen."""
        from moviepy import ImageClip

        total_words = sum(len(s.get("text", "").split()) for s in sections)
        clips = []
        t = 0.0

        for i, section in enumerate(sections):
            words = len(section.get("text", "").split())
            dur = max(2.0, (words / max(total_words, 1)) * total_duration)
            progress = (i + 1) / len(sections)

            img = self._render_progress_bar(progress)
            clip = (
                ImageClip(np.array(img))
                .with_duration(dur)
                .with_start(t)
                .with_position((0, self.H - 6))
            )
            clips.append(clip)
            t += dur

        return clips

    def _render_progress_bar(self, progress: float) -> Image.Image:
        _, _, accent = self.colors
        bar_w = int(self.W * progress)
        img = Image.new("RGBA", (self.W, 6), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, bar_w, 6], fill=(*accent, 220))
        return img

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

            # Channel name text
            tx = 12 + icon_diam + spacing
            draw.text((tx, (img_h - (bbox[3] - bbox[1])) // 2), config.CHANNEL_NAME,
                      font=font, fill=(255, 255, 255, 200))

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
            "hook":    load(96),   # large bold title card text
            "caption": load(config.CAPTION_FONT_SIZE),
            "label":   load(26),
        }
