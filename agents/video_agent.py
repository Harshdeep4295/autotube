"""
Video Agent
Renders a 1920×1080 MP4 using MoviePy 1.x and Pillow.
Creates animated text-on-background slides synced to the voiceover duration.
No external video API required — pure Python rendering.
"""

import logging
import math
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import config

logger = logging.getLogger(__name__)

# Niche color palettes: (bg_start_rgb, bg_end_rgb, accent_rgb)
NICHE_COLORS = {
    "AI & Tech":  ((10, 10, 35),   (3, 3, 18),    (70, 110, 255)),
    "Finance":    ((8, 30, 8),     (3, 12, 3),    (40, 190, 70)),
    "Business":   ((28, 18, 8),    (12, 8, 3),    (240, 150, 25)),
    "Health":     ((32, 8, 8),     (12, 3, 3),    (240, 60, 60)),
    "History":    ((22, 18, 8),    (9, 7, 3),     (190, 140, 45)),
    "default":    ((18, 8, 28),    (7, 3, 12),    (140, 70, 240)),
}


class VideoAgent:
    """Renders a full 1920×1080 MP4 video from script + audio."""

    def __init__(self):
        self.W = config.VIDEO_WIDTH
        self.H = config.VIDEO_HEIGHT
        self.FPS = config.VIDEO_FPS
        self.colors = NICHE_COLORS.get(config.CHANNEL_NICHE, NICHE_COLORS["default"])
        self.fonts = self._load_fonts()

    def render(self, script: Dict, audio_path: str, output_path: str) -> str:
        """
        Args:
            script: Script dict with 'sections' list
            audio_path: Path to the MP3 voiceover
            output_path: Full path to save the output MP4
        Returns:
            output_path on success
        """
        from moviepy.editor import (
            ImageClip, AudioFileClip, CompositeVideoClip,
            concatenate_videoclips
        )

        os.makedirs(Path(output_path).parent, exist_ok=True)

        # Load audio to get total duration
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        logger.info(f"Audio duration: {total_duration:.1f}s — rendering {len(script['sections'])} sections")

        # Build one ImageClip per section
        sections = script.get("sections", [])
        clips = self._build_section_clips(sections, total_duration)

        # Composite: stack section clips sequentially
        video = concatenate_videoclips(clips, method="compose")

        # Add watermark overlay
        video = self._add_watermark(video)

        # Attach audio
        video = video.set_audio(audio)

        # Optional: mix in background music
        video = self._mix_background_music(video, total_duration)

        logger.info(f"Writing video: {output_path}")
        video.write_videofile(
            output_path,
            fps=self.FPS,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp_audio.aac",
            remove_temp=True,
            logger=None,  # suppress moviepy's verbose output
        )
        logger.info(f"Video saved: {output_path}")
        return output_path

    # ── Section clips ─────────────────────────────────────────────────────────

    def _build_section_clips(self, sections: List[Dict], total_duration: float) -> List:
        from moviepy.editor import ImageClip

        total_words = sum(len(s.get("text", "").split()) for s in sections)
        clips = []

        for i, section in enumerate(sections):
            section_words = len(section.get("text", "").split())
            # Proportional duration, minimum 2s per section
            if total_words > 0:
                duration = max(2.0, (section_words / total_words) * total_duration)
            else:
                duration = total_duration / len(sections)

            frame = self._render_section_frame(
                heading=section.get("section_name", f"Section {i+1}").replace("_", " ").title(),
                body=section.get("text", ""),
                section_index=i,
                total_sections=len(sections),
            )
            clip = ImageClip(np.array(frame)).set_duration(duration)
            clips.append(clip)

        return clips

    def _render_section_frame(
        self, heading: str, body: str, section_index: int, total_sections: int
    ) -> Image.Image:
        """Render a single 1920×1080 frame for one script section."""
        bg_start, bg_end, accent = self.colors
        img = Image.new("RGB", (self.W, self.H))
        draw = ImageDraw.Draw(img)

        # Layer 1: Dark gradient background
        for y in range(self.H):
            t = y / self.H
            r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * t)
            g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * t)
            b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * t)
            draw.line([(0, y), (self.W, y)], fill=(r, g, b))

        # Layer 2: Subtle grid overlay
        for x in range(0, self.W, 80):
            draw.line([(x, 0), (x, self.H)], fill=(255, 255, 255, 8))
        for y in range(0, self.H, 80):
            draw.line([(0, y), (self.W, y)], fill=(255, 255, 255, 8))

        # Layer 3: Left accent bar
        draw.rectangle([0, 0, 6, self.H], fill=accent)

        # Layer 4: Section heading (top-left)
        draw.text((40, 40), heading.upper(), font=self.fonts["label"], fill=(*accent, 200))

        # Layer 5: Body text (centered, word-wrapped)
        body_lines = self._wrap_text(body, self.fonts["body"], self.W - 160)
        y_start = self.H // 2 - (len(body_lines) * 60) // 2
        for i, line in enumerate(body_lines[:12]):  # max 12 lines visible
            draw.text((80, y_start + i * 62), line, font=self.fonts["body"], fill=(255, 255, 255))

        # Layer 6: Progress bar (bottom)
        bar_w = int(self.W * (section_index + 1) / total_sections)
        draw.rectangle([0, self.H - 6, self.W, self.H], fill=(40, 40, 60))
        draw.rectangle([0, self.H - 6, bar_w, self.H], fill=accent)

        return img

    # ── Watermark ─────────────────────────────────────────────────────────────

    def _add_watermark(self, video):
        from moviepy.editor import ImageClip, CompositeVideoClip

        try:
            wm = Image.new("RGBA", (360, 48), (0, 0, 0, 0))
            draw = ImageDraw.Draw(wm)
            draw.text((8, 8), config.CHANNEL_NAME, font=self.fonts["label"], fill=(255, 255, 255, 55))
            wm_clip = (
                ImageClip(np.array(wm), ismask=False)
                .set_duration(video.duration)
                .set_position(("right", "bottom"))
                .set_opacity(0.4)
            )
            return CompositeVideoClip([video, wm_clip])
        except Exception as e:
            logger.warning(f"Watermark failed (skipping): {e}")
            return video

    # ── Background music ──────────────────────────────────────────────────────

    def _mix_background_music(self, video, duration: float):
        from moviepy.editor import AudioFileClip, CompositeAudioClip
        import moviepy.audio.fx.all as afx

        music_dir = Path(config.MUSIC_DIR)
        music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
        if not music_files:
            return video

        try:
            music_path = str(random.choice(music_files))
            music = AudioFileClip(music_path)
            if music.duration < duration:
                loops = math.ceil(duration / music.duration)
                from moviepy.editor import concatenate_audioclips
                music = concatenate_audioclips([music] * loops)
            music = music.subclip(0, duration).fx(afx.volumex, 0.06)  # -24dB vs voice

            combined = CompositeAudioClip([video.audio, music]) if video.audio else music
            return video.set_audio(combined)
        except Exception as e:
            logger.warning(f"Background music mixing failed (skipping): {e}")
            return video

    # ── Text wrapping ─────────────────────────────────────────────────────────

    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        words = text.split()
        lines: List[str] = []
        current = ""
        dummy = Image.new("RGB", (1, 1))
        d = ImageDraw.Draw(dummy)

        for word in words:
            test = f"{current} {word}".strip()
            bbox = d.textbbox((0, 0), test, font=font)
            if bbox[2] > max_width and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        return lines

    # ── Font loading ──────────────────────────────────────────────────────────

    def _load_fonts(self) -> Dict:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]

        def load(size: int) -> ImageFont.ImageFont:
            for p in candidates:
                try:
                    return ImageFont.truetype(p, size)
                except (IOError, OSError):
                    pass
            return ImageFont.load_default()

        return {
            "body":  load(46),
            "label": load(26),
            "title": load(72),
        }
