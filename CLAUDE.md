# AutoTube — Claude Code Instructions

Autonomous faceless YouTube channel pipeline. Runs 4×/day on GitHub Actions, producing 1 video per run. No server required — GitHub IS the infrastructure.

---

## How to Run Locally

```bash
# Dry run (no upload) — always test this first
.venv/bin/python3 orchestrator.py --dry-run --topic "Artificial Intelligence in 2025"

# Or via convenience script
./run_local.sh --topic "some topic"          # dry run
./run_local.sh --upload --topic "some topic" # live upload
```

Output lands in `outputs/<date>_<id>/video.mp4`. Open with `open outputs/`.

---

## Key Files

| File | Purpose |
|---|---|
| `config.py` | Single source of truth for all settings — edit here first |
| `orchestrator.py` | Pipeline entry point — wires agents together |
| `agents/research_agent.py` | pytrends + Reddit + RSS → scored topic list |
| `agents/script_agent.py` | Claude or Gemini → structured script JSON |
| `agents/voice_agent.py` | edge-tts (primary) + pyttsx3 (fallback) → audio.mp3 |
| `agents/video_agent.py` | Pexels B-roll + Pillow captions → 1920×1080 MP4 |
| `agents/thumbnail_agent.py` | Pillow → 1280×720 JPEG thumbnail |
| `agents/upload_agent.py` | YouTube Data API v3, OAuth2, resumable upload |
| `templates/prompts.py` | All LLM prompt templates — script structure defined here |
| `.github/workflows/daily_pipeline.yml` | 4 cron triggers (09/12/15/18 IST) |

---

## Critical Tech Notes

### MoviePy version is 2.x — NOT 1.x
The installed version is `moviepy==2.2.1`. The API is completely different from 1.x:
- Imports: `from moviepy import VideoFileClip` (not `from moviepy.editor import ...`)
- Chaining: `.with_duration()`, `.with_audio()`, `.with_position()`, `.with_opacity()`, `.with_start()`
- Trim: `.subclipped(start, end)` (not `.subclip()`)
- Resize: `.resized(new_size=(w, h))` (not `.resize()`)
- Crop: `.cropped(x1=, y1=, x2=, y2=)` (not `.crop()`)
- Volume: `from moviepy.audio.fx import MultiplyVolume` then `.with_effects([MultiplyVolume(0.06)])`
- Never use `.set_duration()`, `.set_audio()`, `.set_position()` — these are 1.x methods and will fail silently or crash

### Google Generative AI package
Use `google-genai` (new), NOT `google-generativeai` (deprecated):
```python
from google import genai
from google.genai import types
client = genai.Client(api_key=config.GEMINI_API_KEY)
client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(system_instruction=..., max_output_tokens=4096)
)
```

### IST → UTC conversion
`config.py` auto-converts `UPLOAD_TIMES_IST` to UTC. Edit times in IST only — never touch UTC manually. The `_ist_to_utc()` helper subtracts 330 minutes.

### Script JSON structure
`script_agent.py` requires these keys: `title`, `description`, `tags`, `sections`, `thumbnail_text`.
`video_agent.py` also uses: `visual_queries` (list of 6 cinematic Pexels search terms, one per section) and `hook_title_text` (bold opener text). These are optional with fallbacks.

### Pexels clip caching
Downloaded clips are cached in `outputs/video_cache/` by URL hash. If you change search queries, clear the cache: `rm -rf outputs/video_cache/*`

---

## Config Fields That Matter Most

```python
CHANNEL_NICHE = "AI & Tech"      # Options: AI & Tech | Finance | Business | Health | History | English Learning
                                  # Changing niche auto-switches: subreddits, RSS feeds, accent colors, script angle guidance
CHANNEL_NAME = "AutoTube"        # shown in top-left watermark
SCRIPT_WORD_COUNT = 650          # ~4.5 min — don't increase beyond 800
SCRIPT_MODEL_PROVIDER            # "claude" or "gemini" — set via env var
VIDEO_BACKGROUND_MODE            # "ai_images" (V2, default) or "pexels" (V1) — set via env var / GitHub Variable
MUSIC_ENABLED                    # "true" (default) or "false" — IMPORTANT: only use CC0 music, YouTube deducts 55% for licensed music
DARK_OVERLAY_OPACITY = 0.52      # how dark the footage overlay is (0.4–0.65)
PEXELS_CLIPS_PER_VIDEO = 6       # 1 per section — matches 6-section script (V1/pexels mode only)
```

---

## Common Pitfalls

- **`multiply_volume` AttributeError** — use `MultiplyVolume` effect, not `.multiply_volume()` method
- **`google-generativeai` import** — wrong package; use `google-genai`
- **`python` not found on Mac** — use `.venv/bin/python3` explicitly
- **Pexels returns AI robot clips** — the `visual_queries` field in the script JSON controls this; queries should be cinematic, not topic-literal (e.g. "aerial cityscape" not "artificial intelligence")
- **Video too long** — `SCRIPT_WORD_COUNT` in config.py controls length; 650 = ~4.5 min
- **Font not found** — `video_agent.py` tries multiple system font paths; falls back to PIL default if none found; add your font path to the `candidates` list in `_load_fonts()`

---

## GitHub Actions

- **4 cron triggers**: 03:30, 06:30, 09:30, 12:30 UTC (= 09/12/15/18 IST)
- Each run: 1 video, ~20 min, then commits history files back to repo
- Manual trigger available via Actions tab with `count`, `dry_run`, `force_topic`, `model_provider` inputs
- `SCRIPT_MODEL_PROVIDER` is a GitHub **Variable** (not Secret) — changeable via UI without code push
- `VIDEO_BACKGROUND_MODE` is a GitHub **Variable** — `ai_images` (V2, default) or `pexels` (V1 fallback)
- Logs uploaded as artifact for 14 days even on failure

## Secrets required in GitHub
`ANTHROPIC_API_KEY`, `YOUTUBE_TOKEN_JSON`, `YOUTUBE_CLIENT_SECRETS`, `PEXELS_API_KEY`
