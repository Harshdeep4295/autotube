"""
Music Agent — Auto-fetches CC0 background music from Pixabay.
Tops up data/music/ folder with fresh tracks for video rendering.
"""

import hashlib
import logging
import os
from pathlib import Path

import requests

from config import config

logger = logging.getLogger(__name__)

PIXABAY_MUSIC_API = "https://pixabay.com/api/"


def ensure_music_available(min_tracks: int = 5) -> None:
    """Ensure at least min_tracks CC0 music files exist in data/music/.
    Downloads from Pixabay API if needed. Non-blocking — logs warnings on failure."""
    music_dir = Path(config.MUSIC_DIR)
    music_dir.mkdir(parents=True, exist_ok=True)

    existing = list(music_dir.glob("*.mp3"))
    if len(existing) >= min_tracks:
        logger.info(f"Music library OK: {len(existing)} tracks available")
        return

    needed = min_tracks - len(existing)
    logger.info(f"Music library needs {needed} more tracks — fetching from Pixabay...")

    api_key = config.PIXABAY_API_KEY
    if not api_key:
        logger.warning("No PIXABAY_API_KEY set — skipping music auto-fetch")
        return

    try:
        resp = requests.get(
            PIXABAY_MUSIC_API,
            params={
                "key": api_key,
                "type": "music",
                "category": "backgrounds",
                "per_page": min(needed + 5, 20),
                "safesearch": "true",
                "order": "popular",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("hits", [])
        if not hits:
            logger.warning("Pixabay returned no music results")
            return

        downloaded = 0
        for hit in hits:
            if downloaded >= needed:
                break

            audio_url = hit.get("previewURL") or hit.get("audio")
            if not audio_url:
                continue

            track_id = hit.get("id", hashlib.md5(audio_url.encode()).hexdigest()[:8])
            filename = f"pixabay_{track_id}.mp3"
            filepath = music_dir / filename

            if filepath.exists():
                continue

            try:
                audio_resp = requests.get(audio_url, timeout=60)
                audio_resp.raise_for_status()
                filepath.write_bytes(audio_resp.content)
                downloaded += 1
                logger.info(f"Downloaded music: {filename} ({len(audio_resp.content) // 1024}KB)")
            except Exception as e:
                logger.warning(f"Failed to download track {track_id}: {e}")

        logger.info(f"Music fetch complete: {downloaded} new tracks downloaded")

    except Exception as e:
        logger.warning(f"Music auto-fetch failed (non-blocking): {e}")
