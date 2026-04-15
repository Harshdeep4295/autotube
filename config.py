"""
config.py — Central configuration for AutoTube.

All tunables live here. Edit CHANNEL_NICHE and CHANNEL_NAME before first run.
Model provider is controlled by the SCRIPT_MODEL_PROVIDER env var (default: "claude").
Upload times are set in IST and auto-converted to UTC internally.
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()  # loads .env file if present (local dev); GitHub Actions uses Secrets


def _ist_to_utc(ist_time: str) -> str:
    """Convert IST time string (HH:MM) to UTC by subtracting 5h30m."""
    h, m = map(int, ist_time.split(":"))
    total_minutes = h * 60 + m - 330  # subtract 5h30m = 330 min
    total_minutes = total_minutes % (24 * 60)  # wrap around midnight
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


@dataclass
class Config:

    # ── Model switch ─────────────────────────────────────────────────────────
    # Set SCRIPT_MODEL_PROVIDER=gemini in env/GitHub Variables to switch.
    # Changing this variable requires no code change — just update the GitHub
    # Actions Variable (Settings → Variables → SCRIPT_MODEL_PROVIDER).
    SCRIPT_MODEL_PROVIDER: str = field(
        default_factory=lambda: os.getenv("SCRIPT_MODEL_PROVIDER", "claude")
    )

    # ── Claude settings ───────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_TOKENS: int = 4096
    CLAUDE_RETRIES: int = 3
    CLAUDE_BACKOFF: float = 2.0  # seconds; doubles each retry

    # ── Gemini settings (optional — for future switch) ────────────────────────
    GEMINI_API_KEY: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # ── Channel settings ──────────────────────────────────────────────────────
    # Change these to match your YouTube channel before the first run.
    CHANNEL_NICHE: str = "AI & Tech"   # Options: AI & Tech | Finance | Business | Health | History
    CHANNEL_NAME: str = "AutoTube"   # Your actual channel name (shown in watermark)

    # ── Research ──────────────────────────────────────────────────────────────
    SUBREDDITS: List[str] = field(default_factory=lambda: [
        "technology", "singularity", "artificial", "MachineLearning",
        "ChatGPT", "OpenAI", "investing", "science"
    ])
    TRENDS_GEO: str = "US"
    TRENDS_CATEGORY: int = 0       # 0 = all categories; 5 = Tech; 7 = Finance
    TOPIC_HISTORY_DAYS: int = 30   # deduplication window (skip topics used recently)
    TOPICS_PER_RUN: int = 4        # how many scored topics to fetch (pick top N)

    # ── Script / content ──────────────────────────────────────────────────────
    SCRIPT_WORD_COUNT: int = 650   # ~4.5 min at 150 wpm
    TARGET_VIDEO_SECONDS: int = 270  # 4.5 minutes

    # ── Voice (edge-tts — 100% free) ──────────────────────────────────────────
    TTS_VOICE: str = "en-US-GuyNeural"   # US male, authoritative tone
    TTS_RATE: str = "+8%"                # slightly faster = more engaging
    TTS_PITCH: str = "+0Hz"

    # ── Video rendering ───────────────────────────────────────────────────────
    VIDEO_WIDTH: int = 1920
    VIDEO_HEIGHT: int = 1080
    VIDEO_FPS: int = 24

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    THUMB_WIDTH: int = 1280
    THUMB_HEIGHT: int = 720
    PEXELS_API_KEY: str = field(
        default_factory=lambda: os.getenv("PEXELS_API_KEY", "")
    )

    # ── Upload schedule (IST) ─────────────────────────────────────────────────
    # Edit these IST times; UTC conversion is automatic.
    UPLOAD_TIMES_IST: List[str] = field(default_factory=lambda: [
        "09:00",  # morning
        "12:00",  # lunch
        "15:00",  # afternoon
        "18:00",  # evening
    ])

    @property
    def UPLOAD_TIMES_UTC(self) -> List[str]:
        return [_ist_to_utc(t) for t in self.UPLOAD_TIMES_IST]

    # ── YouTube API ───────────────────────────────────────────────────────────
    YOUTUBE_CLIENT_SECRETS: str = "client_secrets.json"
    YOUTUBE_TOKEN_FILE: str = "data/youtube_token.json"
    VIDEO_CATEGORY_ID: str = "28"   # 28 = Science & Technology
    VIDEO_PRIVACY: str = "public"
    VIDEO_MADE_FOR_KIDS: bool = False

    # ── Video caption / B-roll settings ──────────────────────────────────────
    VIDEO_CACHE_DIR: str = "outputs/video_cache"   # cached Pexels clips
    PEXELS_CLIPS_PER_VIDEO: int = 6                # 1 unique clip per section
    CAPTION_FONT_SIZE: int = 52
    CAPTION_WORDS_PER_LINE: int = 10               # wrap captions at this many words
    DARK_OVERLAY_OPACITY: float = 0.52             # darkness over footage for text contrast

    # ── Paths ─────────────────────────────────────────────────────────────────
    DATA_DIR: str = "data"
    OUTPUT_DIR: str = "outputs"
    LOG_DIR: str = "logs"
    MUSIC_DIR: str = "data/music"
    HISTORY_FILE: str = "data/topics_history.json"
    POSTED_FILE: str = "data/posted_videos.json"

    # ── Supabase (topic history database) ────────────────────────────────────
    # Create free project at supabase.com → Settings → API → copy URL + anon key
    # If not set, falls back to local data/topics_history.json
    SUPABASE_URL: str = field(
        default_factory=lambda: os.getenv("SUPABASE_URL", "")
    )
    SUPABASE_KEY: str = field(
        default_factory=lambda: os.getenv("SUPABASE_ANON_KEY", "")
    )

    # ── Failure handling ──────────────────────────────────────────────────────
    SKIP_ON_FAIL: bool = True   # skip failed videos and continue pipeline


config = Config()
