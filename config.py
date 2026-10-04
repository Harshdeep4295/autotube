"""
config.py — Central configuration for AutoTube.

All tunables live here and are read from environment variables (.env locally,
GitHub Secrets / repo Variables in Actions).
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()  # loads .env file if present (local dev); GitHub Actions uses Secrets


@dataclass
class Config:

    # ── Free-only mode (default ON) ───────────────────────────────────────────
    # The pipeline only has free providers (Gemini free tier → Groq free tier). With
    # FREE_ONLY on it also refuses to start if the environment still asks for one of the
    # old paid services (see paid_features_in_use).
    FREE_ONLY: bool = field(
        default_factory=lambda: os.getenv("FREE_ONLY", "true").lower() != "false"
    )
    # Free-tier model lists, tried in order. Free tiers change often — override
    # with comma-separated env vars instead of editing code.
    GEMINI_FREE_MODELS: List[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv(
            "GEMINI_FREE_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash"
        ).split(",") if m.strip()
    ])
    # Gemini 3.x thinking tokens count against max_output_tokens; "low" keeps long JSON
    # answers from being cut off. "" or "default" = don't send a thinking setting.
    GEMINI_THINKING_LEVEL: str = field(default_factory=lambda: os.getenv("GEMINI_THINKING_LEVEL", "low"))
    GROQ_FREE_MODELS: List[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv(
            "GROQ_FREE_MODELS", "openai/gpt-oss-120b,qwen/qwen3-32b"
        ).split(",") if m.strip()
    ])
    # Free keys: https://aistudio.google.com (Gemini), https://console.groq.com (Groq)
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    GROQ_API_KEY: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))

    # ── Video style ───────────────────────────────────────────────────────────
    # "explainer" → Remotion animated explainer (default, see docs/PLAN_EXPLAINER_AND_AI_VIDEO.md)
    # "kids"      → "Explained Like You're 5" story video (see docs/PLAN_KIDS_EXPLAINER.md)
    VIDEO_STYLE: str = field(default_factory=lambda: os.getenv("VIDEO_STYLE", "explainer").lower())
    EXPLAINER_DIR: str = "video/explainer"
    EXPLAINER_MIN_SECONDS: int = field(default_factory=lambda: int(os.getenv("EXPLAINER_MIN_SECONDS", "480")))
    EXPLAINER_TARGET_WORDS: int = field(default_factory=lambda: int(os.getenv("EXPLAINER_TARGET_WORDS", "1100")))
    # Auto-publish: "HH:MM" (UTC). Uploads stay Private and YouTube publishes them at the next
    # occurrence of this time — the gap is your review window (set the video back to Private in
    # Studio to stop it). Empty = stay Private until you publish by hand.
    # 18:30 UTC = 2:30 pm US Eastern / 12:00 am IST (weekday long-form sweet spot 2-5 pm local).
    EXPLAINER_PUBLISH_AT_UTC: str = field(default_factory=lambda: os.getenv("EXPLAINER_PUBLISH_AT_UTC", "").strip())
    # Narration pace incl. pauses, measured on a real run: 1426 words → 699 s ≈ 122 wpm
    # (the 89 s fixture looked faster because of its short lines). 125 keeps the estimate
    # slightly low, so a script that passes the pre-render gate also passes the 480 s QA check.
    EXPLAINER_WPM: int = field(default_factory=lambda: int(os.getenv("EXPLAINER_WPM", "125")))
    # Playlist title every explainer upload is added to (created on first use). Empty = none.
    EXPLAINER_PLAYLIST: str = field(default_factory=lambda: os.getenv("EXPLAINER_PLAYLIST", "").strip())

    # ── Kids track: "Explained Like You're 5" (VIDEO_STYLE=kids, see docs/PLAN_KIDS_EXPLAINER.md) ──
    # 2-3 minute story videos (recurring cast + prop kit, pycairo renderer). All ages, NOT made for kids.
    KIDS_TARGET_WORDS: int = field(default_factory=lambda: int(os.getenv("KIDS_TARGET_WORDS", "300")))
    KIDS_MIN_SECONDS: int = field(default_factory=lambda: int(os.getenv("KIDS_MIN_SECONDS", "90")))
    KIDS_MAX_SECONDS: int = field(default_factory=lambda: int(os.getenv("KIDS_MAX_SECONDS", "180")))
    # Slow, friendly pace incl. pauses (the stock-market POC: 318 words → 119 s ≈ 160 wpm incl. gaps)
    KIDS_WPM: int = field(default_factory=lambda: int(os.getenv("KIDS_WPM", "140")))
    KIDS_TTS: str = field(default_factory=lambda: os.getenv("KIDS_TTS", "kokoro").lower())
    KIDS_KOKORO_VOICE: str = field(default_factory=lambda: os.getenv("KIDS_KOKORO_VOICE", "af_heart"))
    KIDS_KOKORO_SPEED: float = field(default_factory=lambda: float(os.getenv("KIDS_KOKORO_SPEED", "0.92")))
    PIPER_MODEL: str = field(default_factory=lambda: os.getenv("PIPER_MODEL", ""))
    KIDS_PUBLISH_AT_UTC: str = field(default_factory=lambda: os.getenv("KIDS_PUBLISH_AT_UTC", "").strip())
    # Playlist title every kids upload is added to (created on first use); also the first tag.
    KIDS_PLAYLIST: str = field(default_factory=lambda: os.getenv("KIDS_PLAYLIST", "Explained Like You're 5"))
    # Vertical 9:16 cut of every kids video, uploaded as a second video (a YouTube Short).
    KIDS_SHORTS: bool = field(default_factory=lambda: os.getenv("KIDS_SHORTS", "true").lower() != "false")
    # "HH:MM" UTC for the Short; empty = same time as the full video (KIDS_PUBLISH_AT_UTC).
    KIDS_SHORT_PUBLISH_AT_UTC: str = field(default_factory=lambda: os.getenv("KIDS_SHORT_PUBLISH_AT_UTC", "").strip())
    # "mixed" = headline→concept first, evergreen bank as fallback; "bank" = bank only; "feed" = headlines only
    KIDS_TOPIC_MODE: str = field(default_factory=lambda: os.getenv("KIDS_TOPIC_MODE", "mixed").lower())
    KIDS_TOPICS_FILE: str = "data/kids_topics.json"
    KIDS_HISTORY_FILE: str = "data/kids_topics_history.json"

    # ── Voice (Kokoro, offline, Apache-2.0) ───────────────────────────────────
    KOKORO_VOICE: str = field(default_factory=lambda: os.getenv("KOKORO_VOICE", "am_michael"))
    KOKORO_SPEED: float = field(default_factory=lambda: float(os.getenv("KOKORO_SPEED", "1.05")))
    # "whisper" = word timings from faster-whisper (falls back automatically), "proportional" = estimate
    WORD_TIMINGS: str = field(default_factory=lambda: os.getenv("WORD_TIMINGS", "whisper").lower())

    # ── Channel ───────────────────────────────────────────────────────────────
    CHANNEL_NAME: str = field(default_factory=lambda: os.getenv("CHANNEL_NAME", "Run It Local"))
    CHANNEL_TAGLINE: str = field(default_factory=lambda: os.getenv(
        "CHANNEL_TAGLINE", "Free & open-source AI you can run yourself"))
    # Sub-niche (2026-09-29): practical, free / open-source AI tools people can run and
    # use themselves. Evergreen how-to + explainers, fits the animated scene catalogue.
    CHANNEL_SUBNICHE: str = field(default_factory=lambda: os.getenv(
        "CHANNEL_SUBNICHE",
        "Practical AI: free and open-source AI tools you can run and use yourself",
    ))
    # A research topic must contain at least one of these (case-insensitive) to be used.
    NICHE_KEYWORDS: List[str] = field(default_factory=lambda: [
        k.strip().lower() for k in os.getenv("NICHE_KEYWORDS", (
            "ai,llm,gpt,chatgpt,claude,gemini,llama,mistral,qwen,deepseek,ollama,lm studio,"
            "open-source model,open source model,open-weight,local model,self-host,"
            "stable diffusion,whisper,transformer,neural,machine learning,agent,copilot,"
            "prompt,inference,gpu,quantiz,rag,embedding,fine-tun,hugging face,automation"
        )).split(",") if k.strip()
    ])

    # ── Research (agents/research_agent.py) ───────────────────────────────────
    TOPIC_HISTORY_DAYS: int = 30   # deduplication window (skip topics used recently)
    TOPICS_PER_RUN: int = 1        # 1 video/day — give each video room to breathe
    # Reddit often blocks cloud IPs; best-effort
    ACTIVE_SUBREDDITS: List[str] = field(default_factory=lambda: [
        "LocalLLaMA", "ollama", "selfhosted", "ArtificialInteligence", "OpenAI", "StableDiffusion",
    ])

    # ── YouTube upload ────────────────────────────────────────────────────────
    # YOUTUBE_TOKEN_JSON is either the token JSON itself or a path to it.
    YOUTUBE_TOKEN_FILE: str = field(
        default_factory=lambda: os.getenv("YOUTUBE_TOKEN_JSON", "data/youtube_token.json")
    )
    VIDEO_CATEGORY_ID: str = "28"   # 28 = Science & Technology
    # Uploads are PRIVATE by default: a human publishes after review (or *_PUBLISH_AT_UTC does).
    VIDEO_PRIVACY: str = field(default_factory=lambda: os.getenv("VIDEO_PRIVACY", "private"))
    # Sets status.containsSyntheticMedia (YouTube "altered or synthetic content" disclosure).
    VIDEO_SYNTHETIC_MEDIA: bool = field(
        default_factory=lambda: os.getenv("VIDEO_SYNTHETIC_MEDIA", "true").lower() != "false"
    )
    VIDEO_MADE_FOR_KIDS: bool = False
    PLAYLIST_ENABLED: bool = field(
        default_factory=lambda: os.getenv("PLAYLIST_ENABLED", "true").lower() != "false"
    )

    # ── Background music ──────────────────────────────────────────────────────
    # Only CC0 / royalty-free tracks in data/music/ (licensed music costs revenue share).
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

    def paid_features_in_use(self) -> List[str]:
        """Old paid-service switches still set in the environment. Empty list = free-only safe.
        The code for these services is gone; this catches a leftover secret or variable."""
        paid = []
        provider = os.getenv("SCRIPT_MODEL_PROVIDER", "").lower()
        if provider in ("claude", "bedrock"):
            paid.append(f"SCRIPT_MODEL_PROVIDER={provider} (paid API)")
        if os.getenv("VIDEO_ANIMATION_MODE", "").lower() == "veo":
            paid.append("VIDEO_ANIMATION_MODE=veo (Vertex AI, paid)")
        if os.getenv("GCS_BUCKET_NAME"):
            paid.append("GCS_BUCKET_NAME set (Cloud Storage backup, paid)")
        return paid

    def assert_free_only(self) -> None:
        """Raise if FREE_ONLY is on and a paid service is configured."""
        if not self.FREE_ONLY:
            return
        paid = self.paid_features_in_use()
        if paid:
            raise RuntimeError(
                "FREE_ONLY=true but paid services are configured: " + "; ".join(paid)
                + ". Unset them, or set FREE_ONLY=false to allow paid services."
            )


config = Config()
