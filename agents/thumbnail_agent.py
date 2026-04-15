"""
Thumbnail Agent
Creates high-CTR YouTube thumbnails (1280×720) using Pillow only.
No paid tools. Bold text on dark niche-colored backgrounds.
Optional Pexels stock photo background if PEXELS_API_KEY is set.
"""

import logging
import os
import random
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config import config

logger = logging.getLogger(__name__)

NICHE_COLORS = {
    "AI & Tech":  ((15, 15, 40),   (5, 5, 20),    (80, 120, 255)),
    "Finance":    ((10, 35, 10),   (5, 15, 5),    (50, 200, 80)),
    "Business":   ((30, 20, 10),   (15, 10, 5),   (255, 160, 30)),
    "Health":     ((35, 10, 10),   (15, 5, 5),    (255, 70, 70)),
    "History":    ((25, 20, 10),   (10, 8, 4),    (200, 150, 50)),
    "default":    ((20, 10, 30),   (8, 4, 15),    (150, 80, 255)),
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
            script: Script dict with thumbnail_text, thumbnail_subtext, pexels_search_query
            output_path: Full path to save the thumbnail JPEG
        Returns:
            output_path on success
        """
        os.makedirs(Path(output_path).parent, exist_ok=True)

        thumb_text = script.get("thumbnail_text", script.get("title", "")[:30].upper())
        thumb_subtext = script.get("thumbnail_subtext", "")
        pexels_query = script.get("pexels_search_query", "technology abstract")

        # Step 1: Background
        img = self._create_background(pexels_query)

        # Step 2: Dark left vignette overlay (for text contrast)
        img = self._add_vignette(img)

        # Step 3: Left accent bar
        img = self._add_accent_bar(img)

        # Step 4: Main headline text
        img = self._add_headline(img, thumb_text)

        # Step 5: Sub-text (smaller, accent color)
        if thumb_subtext:
            img = self._add_subtext(img, thumb_subtext)

        # Step 6: Channel badge (bottom-right)
        img = self._add_channel_badge(img)

        img.save(str(output_path), "JPEG", quality=95, optimize=True)
        logger.info(f"Thumbnail saved: {output_path}")
        return output_path

    # ── Background ────────────────────────────────────────────────────────────

    def _create_background(self, pexels_query: str) -> Image.Image:
        if config.PEXELS_API_KEY:
            try:
                return self._fetch_pexels_bg(pexels_query)
            except Exception as e:
                logger.warning(f"Pexels failed (using gradient): {e}")
        return self._gradient_background()

    def _fetch_pexels_bg(self, query: str) -> Image.Image:
        headers = {"Authorization": config.PEXELS_API_KEY}
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            timeout=10,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            raise ValueError("No Pexels photos found")
        photo_url = random.choice(photos)["src"]["large2x"]
        img_data = requests.get(photo_url, timeout=15).content
        img = Image.open(BytesIO(img_data)).convert("RGB")
        img = img.resize((self.W, self.H), Image.LANCZOS)
        # Darken 60% for text readability
        overlay = Image.new("RGB", (self.W, self.H), (0, 0, 0))
        return Image.blend(img, overlay, 0.60)

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
        for x in range(self.W * 3 // 4):
            alpha = int(170 * (1 - x / (self.W * 0.75)))
            draw.line([(x, 0), (x, self.H)], fill=(0, 0, 0, alpha))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _add_accent_bar(self, img: Image.Image) -> Image.Image:
        _, _, accent = self.colors
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 12, self.H], fill=accent)
        return img

    def _add_headline(self, img: Image.Image, text: str) -> Image.Image:
        _, _, accent = self.colors
        draw = ImageDraw.Draw(img)
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
            "badge":    load(26),
        }
