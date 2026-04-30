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
    # SCRIPT_MODEL_PROVIDER controls script generation:
    #   "auto"    — Hybrid (try Claude → fallback Gemini if quota exhausted) [DEFAULT]
    #   "hybrid"  — Same as "auto" (explicit hybrid mode)
    #   "claude"  — Claude only
    #   "gemini"  — Gemini only
    # Change via env var or GitHub Actions Variable (no code change needed).
    SCRIPT_MODEL_PROVIDER: str = field(
        default_factory=lambda: os.getenv("SCRIPT_MODEL_PROVIDER", "auto")
    )

    # ── Claude settings ───────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_TOKENS: int = 4096
    CLAUDE_RETRIES: int = 3
    CLAUDE_BACKOFF: float = 2.0  # seconds; doubles each retry

    # ── Gemini settings (required for hybrid/auto mode fallback) ──────────────
    # Set GEMINI_API_KEY in .env or GitHub Secrets for hybrid fallback.
    # Get free API key from https://ai.google.dev/ (free tier available).
    GEMINI_API_KEY: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # ── Groq settings (tertiary fallback — Claude → Gemini → Groq) ────────────
    # Set GROQ_API_KEY in .env or GitHub Secrets for 3-way fallback resilience.
    # Get free API key from https://console.groq.com/ (free tier available).
    GROQ_API_KEY: str = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY", "")
    )
    GROQ_MODEL: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    GROQ_MODEL_FALLBACK: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL_FALLBACK", "llama-3.1-8b-instant")
    )

    # ── Channel settings ──────────────────────────────────────────────────────
    # Change these to match your YouTube channel before the first run.
    # Options: AI & Tech | Finance | Business | Health | History | English Learning
    CHANNEL_NICHE: str = "AI & Tech"
    CHANNEL_NAME: str = "AutoTube"   # Your actual channel name (shown in watermark)

    # ── Research ──────────────────────────────────────────────────────────────
    # Subreddits are auto-selected based on CHANNEL_NICHE if SUBREDDITS is left empty.
    # Override by setting SUBREDDITS explicitly.
    SUBREDDITS: List[str] = field(default_factory=lambda: [])
    TRENDS_GEO: str = "US"
    TRENDS_CATEGORY: int = 0       # 0 = all categories; 5 = Tech; 7 = Finance
    TOPIC_HISTORY_DAYS: int = 30   # deduplication window (skip topics used recently)
    TOPICS_PER_RUN: int = 4        # how many scored topics to fetch (pick top N)

    # Per-niche subreddit defaults — used when SUBREDDITS is empty
    NICHE_SUBREDDITS: dict = field(default_factory=lambda: {
        "AI & Tech": [
            "technology", "singularity", "artificial", "MachineLearning",
            "ChatGPT", "OpenAI", "programming", "science",
        ],
        "Finance": [
            "personalfinance", "investing", "stocks", "financialindependence",
            "dividends", "SecurityAnalysis", "wallstreetbets", "economy",
        ],
        "Business": [
            "entrepreneur", "smallbusiness", "startups", "business",
            "marketing", "SideProject", "passive_income", "ecommerce",
        ],
        "Health": [
            "nutrition", "fitness", "longevity", "health", "medicine",
            "weightloss", "mentalhealth", "sleep",
        ],
        "History": [
            "history", "AskHistorians", "HistoryMemes", "todayilearned",
            "worldhistory", "AncientHistory", "WW2", "AskHistory",
        ],
        "English Learning": [
            "EnglishLearning", "grammar", "ENGLISH", "languagelearning",
            "LearnEnglish", "linguistics", "teachers", "IELTS",
        ],
    })

    @property
    def ACTIVE_SUBREDDITS(self) -> List[str]:
        """Returns explicit SUBREDDITS if set, otherwise uses niche defaults."""
        if self.SUBREDDITS:
            return self.SUBREDDITS
        return self.NICHE_SUBREDDITS.get(self.CHANNEL_NICHE, self.NICHE_SUBREDDITS["AI & Tech"])

    # ── Script / content ──────────────────────────────────────────────────────
    SCRIPT_WORD_COUNT: int = 750   # ~5 min at 150 wpm
    TARGET_VIDEO_SECONDS: int = 300  # 5 minutes

    # ── Voice (edge-tts — 100% free) ──────────────────────────────────────────
    TTS_VOICE: str = "en-US-JennyNeural"  # US female, warm and professional
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
    PIXABAY_API_KEY: str = field(
        default_factory=lambda: os.getenv("PIXABAY_API_KEY", "")
    )
    VIDEO_PIPELINE_VERSION: str = field(
        default_factory=lambda: os.getenv("VIDEO_PIPELINE_VERSION", "v1")
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
    YOUTUBE_TOKEN_FILE: str = field(
        default_factory=lambda: os.getenv("YOUTUBE_TOKEN_JSON", "data/youtube_token.json")
    )
    VIDEO_CATEGORY_ID: str = "28"   # 28 = Science & Technology
    VIDEO_PRIVACY: str = "public"
    VIDEO_MADE_FOR_KIDS: bool = False

    # ── Video background mode ─────────────────────────────────────────────────
    # "ai_images" → Pollinations.ai AI-generated images + Ken Burns effect (V2, default)
    # "pexels"    → Pexels stock B-roll clips (V1, legacy — reverts by setting env var)
    # Switch without code change: set VIDEO_BACKGROUND_MODE in .env or GitHub Variable.
    VIDEO_BACKGROUND_MODE: str = field(
        default_factory=lambda: os.getenv("VIDEO_BACKGROUND_MODE", "ai_images")
    )

    # ── Video animation mode ──────────────────────────────────────────────────
    # "veo"        → GCP Vertex AI Veo 3.1 native video (requires GCP credits — free $300 trial)
    # "kling"      → Kling API video generation (requires API key)
    # "pika"       → Pika video generation (requires API key)
    # "ken_burns"  → Pollinations AI images + FFmpeg zoompan animation (COMPLETELY FREE ✓)
    # Default: "veo" (best quality, uses GCP free credits). Falls back to Ken Burns if quota exceeded.
    VIDEO_ANIMATION_MODE: str = field(
        default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "veo")
    )

    # ── Video caption / B-roll settings ──────────────────────────────────────
    VIDEO_CACHE_DIR: str = "outputs/video_cache"   # cached Pexels clips and AI images
    PEXELS_CLIPS_PER_VIDEO: int = 6                # Dynamic per actual sections (4-8 based on script complexity)
    CAPTION_FONT_SIZE: int = 52
    CAPTION_WORDS_PER_LINE: int = 10               # wrap captions at this many words
    DARK_OVERLAY_OPACITY: float = 0.52             # darkness over footage for text contrast

    # ── Background music ──────────────────────────────────────────────────────
    # IMPORTANT: YouTube deducts 55% of earnings for licensed music.
    # Only use CC0 / royalty-free music in data/music/.
    # Set MUSIC_ENABLED=false to disable background music entirely.
    MUSIC_ENABLED: bool = field(
        default_factory=lambda: os.getenv("MUSIC_ENABLED", "true").lower() != "false"
    )

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

    # ── GCP Configuration (for GCS backup & Veo video generation) ──────────────
    GCP_PROJECT_ID: str = field(
        default_factory=lambda: os.getenv("GCP_PROJECT_ID", "")
    )
    GCP_GCS_BUCKET: str = field(
        default_factory=lambda: os.getenv("GCP_GCS_BUCKET", "autotube-veo-output")
    )

    # ── Failure handling ──────────────────────────────────────────────────────
    SKIP_ON_FAIL: bool = True   # skip failed videos and continue pipeline


config = Config()
