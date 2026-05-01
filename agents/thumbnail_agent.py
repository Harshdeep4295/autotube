"""
Thumbnail Agent
Creates high-CTR YouTube thumbnails (1280×720) using Pillow only.
No paid tools. Bold text on AI-generated backgrounds (Pollinations.ai — free, no key).
Falls back to gradient if image generation fails.
"""

import hashlib
import logging
import os
import random
import urllib.parse
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config import config

logger = logging.getLogger(__name__)

NICHE_COLORS = {
    "AI & Tech":        ((15, 15, 40),   (5, 5, 20),    (80, 120, 255)),
    "Finance":          ((10, 35, 10),   (5, 15, 5),    (50, 200, 80)),
    "Business":         ((30, 20, 10),   (15, 10, 5),   (255, 160, 30)),
    "Health":           ((35, 10, 10),   (15, 5, 5),    (255, 70, 70)),
    "History":          ((25, 20, 10),   (10, 8, 4),    (200, 150, 50)),
    "English Learning": ((10, 35, 20),   (4, 15, 8),    (40, 215, 120)),
    "default":          ((20, 10, 30),   (8, 4, 15),    (150, 80, 255)),
}


class ThumbnailAgent:
    """Creates YouTube thumbnails using Pillow."""

    def __init__(self):
        self.W = config.THUMB_WIDTH
        self.H = config.THUMB_HEIGHT
        self.colors = NICHE_COLORS.get(config.CHANNEL_NICHE, NICHE_COLORS["default"])
        self.fonts = self._load_fonts()

    def create(self, script: Dict, output_path: str) -> str:
        """
        Args:
            script: Script dict with thumbnail_text, thumbnail_subtext, thumbnail_stat
            output_path: Full path to save the thumbnail JPEG
        Returns:
            output_path on success
        """
        os.makedirs(Path(output_path).parent, exist_ok=True)

        # Enforce 3-4 word max on thumbnail text
        thumb_text = script.get("thumbnail_text", script.get("title", "")[:25].upper())
        thumb_words = thumb_text.split()
        if len(thumb_words) > 5:
            thumb_text = " ".join(thumb_words[:4])
        thumb_text = thumb_text.upper()

        thumb_subtext = script.get("thumbnail_subtext", "")
        thumb_stat = script.get("thumbnail_stat", "")  # bold number badge e.g. "47", "$50K"
        visual_query = script.get("pexels_search_query", "technology abstract")

        # Step 1: Background — AI-generated via Pollinations.ai (free, unique every video)
        img = self._create_background(visual_query, script.get("title", ""))

        # Step 2: Dark left vignette overlay (for text contrast)
        img = self._add_vignette(img)

        # Step 3: Left accent bar
        img = self._add_accent_bar(img)

        # Step 4: Main headline text
        img = self._add_headline(img, thumb_text)

        # Step 5: Sub-text (smaller, accent color)
        if thumb_subtext:
            img = self._add_subtext(img, thumb_subtext)

        # Step 6: Stat badge (bold number/stat, top-right — high-CTR pattern)
        if thumb_stat:
            img = self._add_stat_badge(img, thumb_stat)

        # Step 7: Channel badge (bottom-right)
        img = self._add_channel_badge(img)

        img.save(str(output_path), "JPEG", quality=95, optimize=True)
        logger.info(f"Thumbnail saved: {output_path}")
        return output_path

    # ── Background ────────────────────────────────────────────────────────────

    def _create_background(self, visual_query: str, title: str = "") -> Image.Image:
        """Use Pollinations.ai (free, no key) for unique AI-generated thumbnails."""
        try:
            return self._fetch_ai_bg(visual_query, title)
        except Exception as e:
            logger.warning(f"AI background failed (using gradient): {e}")
        return self._gradient_background()

    def _fetch_ai_bg(self, visual_query: str, title: str = "") -> Image.Image:
        """Download a Pollinations.ai background image sized for thumbnail (1280×720)."""
        prompt = f"cinematic dramatic {visual_query}, dark moody lighting, high contrast, professional photography, no text, no watermark"
        prompt_hash = hashlib.md5(f"thumb_{prompt}".encode()).hexdigest()[:12]
        cache_path = Path(config.VIDEO_CACHE_DIR) / f"thumb_{prompt_hash}.jpg"

        if cache_path.exists() and cache_path.stat().st_size > 5_000:
            img = Image.open(cache_path).convert("RGB")
            return img.resize((self.W, self.H), Image.LANCZOS)

        encoded = urllib.parse.quote(prompt)
        seed = random.randint(1, 99999)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={self.W}&height={self.H}&nologo=true&model=flux&seed={seed}"
        )
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()

        os.makedirs(config.VIDEO_CACHE_DIR, exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(resp.content)

        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img = img.resize((self.W, self.H), Image.LANCZOS)
        # Darken 55% for text readability
        overlay = Image.new("RGB", (self.W, self.H), (0, 0, 0))
        result = Image.blend(img, overlay, 0.55)
        logger.info(f"AI thumbnail background generated: {cache_path.name}")
        return result

    def _gradient_background(self) -> Image.Image:
        bg_start, bg_end, _ = self.colors
        img = Image.new("RGB", (self.W, self.H))
        draw = ImageDraw.Draw(img)
        for y in range(self.H):
            t = y / self.H
            r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * t)
            g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * t)
            b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * t)
            draw.line([(0, y), (self.W, y)], fill=(r, g, b))
        return img

    # ── Overlays ──────────────────────────────────────────────────────────────

    def _add_vignette(self, img: Image.Image) -> Image.Image:
        overlay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        if config.IS_SHORTS:
            # For Shorts: bottom gradient for text contrast
            for y in range(self.H // 2, self.H):
                alpha = int(170 * (1 - (self.H - y) / (self.H * 0.5)))
                draw.line([(0, y), (self.W, y)], fill=(0, 0, 0, alpha))
        else:
            # For landscape: left gradient
            for x in range(self.W * 3 // 4):
                alpha = int(170 * (1 - x / (self.W * 0.75)))
                draw.line([(x, 0), (x, self.H)], fill=(0, 0, 0, alpha))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _add_accent_bar(self, img: Image.Image) -> Image.Image:
        # Skip accent bar for Shorts (already has bottom vignette for text)
        if config.IS_SHORTS:
            return img
        _, _, accent = self.colors
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 12, self.H], fill=accent)
        return img

    def _add_headline(self, img: Image.Image, text: str) -> Image.Image:
        _, _, accent = self.colors
        draw = ImageDraw.Draw(img)

        if config.IS_SHORTS:
            # For Shorts: position at bottom center
            lines = self._wrap_text(text, self.fonts["headline"], self.W - 40)
            # Calculate total height needed
            line_height = 110
            total_height = len(lines[:3]) * line_height
            # Start near bottom with some padding
            y = self.H - 500

            for line in lines[:3]:
                # Center horizontally
                bbox = draw.textbbox((0, 0), line, font=self.fonts["headline"])
                line_width = bbox[2] - bbox[0]
                x = (self.W - line_width) // 2
                # Drop shadow
                draw.text((x + 3, y + 3), line, font=self.fonts["headline"], fill=(0, 0, 0, 180))
                draw.text((x, y), line, font=self.fonts["headline"], fill=(255, 255, 255))
                y += line_height
        else:
            # For landscape: position at top-left
            lines = self._wrap_text(text, self.fonts["headline"], 720)
            y = 120
            for line in lines[:3]:
                # Drop shadow
                draw.text((43, y + 3), line, font=self.fonts["headline"], fill=(0, 0, 0, 180))
                draw.text((40, y), line, font=self.fonts["headline"], fill=(255, 255, 255))
                y += 110
        return img

    def _add_subtext(self, img: Image.Image, text: str) -> Image.Image:
        _, _, accent = self.colors
        draw = ImageDraw.Draw(img)
        # Position below headline
        draw.text((43, self.H // 2 + 30), text, font=self.fonts["subtext"], fill=accent)
        return img

    def _add_stat_badge(self, img: Image.Image, stat: str) -> Image.Image:
        """Bold number/stat badge in top-right corner — high-CTR pattern (e.g. '47', '$50K', '10X')."""
        _, _, accent = self.colors
        draw = ImageDraw.Draw(img)
        stat_text = str(stat).upper().strip()[:8]  # cap length
        font = self.fonts["stat"]

        bbox = draw.textbbox((0, 0), stat_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x, pad_y = 24, 16
        badge_w = tw + pad_x * 2
        badge_h = th + pad_y * 2

        # Position: top-right, with margin
        bx = self.W - badge_w - 30
        by = 30

        # Accent-colored background pill
        badge_layer = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge_layer)
        bd.rounded_rectangle([bx, by, bx + badge_w, by + badge_h], radius=14,
                              fill=(*accent, 230))
        img = Image.alpha_composite(img.convert("RGBA"), badge_layer).convert("RGB")

        # Draw stat text in black (high contrast on accent color)
        draw = ImageDraw.Draw(img)
        draw.text((bx + pad_x, by + pad_y), stat_text, font=font, fill=(0, 0, 0, 255))
        return img

    def _add_channel_badge(self, img: Image.Image) -> Image.Image:
        draw = ImageDraw.Draw(img)
        badge_text = config.CHANNEL_NAME
        bbox = draw.textbbox((0, 0), badge_text, font=self.fonts["badge"])
        bw = bbox[2] - bbox[0] + 24
        bh = bbox[3] - bbox[1] + 14
        bx = self.W - bw - 20
        by = self.H - bh - 20
        # Semi-transparent pill background
        badge = Image.new("RGBA", (bw, bh), (0, 0, 0, 120))
        img.paste(Image.alpha_composite(badge, Image.new("RGBA", (bw, bh), (0, 0, 0, 0))),
                  (bx, by), badge)
        draw.text((bx + 12, by + 7), badge_text, font=self.fonts["badge"], fill=(200, 200, 200))
        return img

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _wrap_text(self, text: str, font, max_width: int):
        words = text.split()
        lines = []
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
            "headline": load(88),
            "subtext":  load(52),
            "stat":     load(72),   # bold number badge (top-right)
            "badge":    load(26),
        }
