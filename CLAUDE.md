# AutoTube — Claude Code Instructions

Autonomous faceless YouTube channel pipeline. Generates 8+ min videos daily with AI images + ken_burns animation. Targeting GitHub Actions for free compute (2,000 min/month).

---

## Git Workflow — IMPORTANT

**Never run `git add`, `git commit`, or `git push` without explicit instruction from the user.**

After code changes: tell user what changed, suggest `git diff` review, suggest commit message.

---

## How to Run

```bash
# Dry run (always test first)
.venv/bin/python3 orchestrator.py --dry-run --topic "AI Tools 2025"

# Hindi / Spanish
LANGUAGE=hi .venv/bin/python3 orchestrator.py --dry-run --topic "AI Tools"
LANGUAGE=es .venv/bin/python3 orchestrator.py --dry-run --topic "AI Tools"

# Shorts from existing videos
python orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views --dry-run

# With approval queue
APPROVAL_REQUIRED=true .venv/bin/python3 orchestrator.py --dry-run --topic "AI Tools"
```

Output: `outputs/<date>_<id>/video.mp4`

---

## Key Files

| File | Purpose |
|---|---|
| `config.py` | Single source of truth for all settings |
| `orchestrator.py` | Pipeline entry point — wires agents together |
| `agents/video_agent.py` | Parallel FFmpeg render (4-at-a-time) + MoviePy fallback |
| `agents/research_agent.py` | pytrends + Reddit + RSS + YouTube comments → scored topics |
| `agents/script_agent.py` | Claude/Gemini/Groq → structured script JSON |
| `agents/voice_agent.py` | edge-tts (primary) + pyttsx3 (fallback) → audio.mp3 |
| `agents/upload_agent.py` | YouTube Data API v3, OAuth2, resumable upload, playlists |
| `agents/thumbnail_agent.py` | Pillow → JPEG thumbnail |
| `agents/music_agent.py` | Pixabay CC0 music auto-fetch → `data/music/` |
| `agents/analytics_agent.py` | YouTube Analytics → topic boost scoring |
| `templates/prompts.py` | All LLM prompt templates |

---

## Video Render Pipeline (2026-05-16)

### Parallel FFmpeg Path (default, 8x faster)

The render uses `_render_parallel_ffmpeg` — no MoviePy frame iteration:

1. **Fetch AI images** from Pollinations (free, no API key)
2. **Generate ken_burns segments** — 4 parallel FFmpeg processes at a time (safe on 2-core/8GB RAM)
3. **Concat segments** — `ffmpeg -f concat -c copy` (instant, zero re-encode)
4. **Final composite** — single FFmpeg pass: dark overlay + hook card + watermark + section titles + audio/music mix

**Performance:**
- Render time: ~10 seconds (vs ~82s with old MoviePy streaming path)
- Peak RAM: ~212 MB (vs ~942 MB before)
- No OOM risk on e2-standard-2 (8GB) or GitHub Actions (7GB)
- Falls back to MoviePy path if FFmpeg composite fails

**Caching:** Segments cached at `outputs/video_cache/fx_*.mp4` by content hash. Repeat renders are instant.

**Key methods in `video_agent.py`:**
- `_render_parallel_ffmpeg()` — orchestrates the fast path
- `_generate_segments_parallel()` — ThreadPoolExecutor, batch_size=4
- `_generate_ken_burns_segment()` — single segment FFmpeg zoompan
- `_ffmpeg_concat_segments()` — concat demuxer with absolute paths
- `_ffmpeg_final_composite()` — filter_complex: overlays + audio mix

---

## Critical Tech Notes

### MoviePy 2.x (NOT 1.x)
- Imports: `from moviepy import VideoFileClip`
- Methods: `.with_duration()`, `.subclipped()`, `.resized()`, `.cropped()`, `.with_effects([MultiplyVolume(0.06)])`
- Never use 1.x methods (`.set_duration()`, `.subclip()`, `.resize()`)

### Google Generative AI
Use `google-genai` (NOT `google-generativeai`):
```python
from google import genai
from google.genai import types
client = genai.Client(api_key=config.GEMINI_API_KEY)
```

### Script JSON structure
Required keys: `title`, `description`, `tags`, `sections`, `thumbnail_text`
Optional: `visual_queries` (8 cinematic search terms), `hook_title_text`

### IST → UTC
`config.py` auto-converts `UPLOAD_TIMES_IST` to UTC. Edit IST only.

---

## Config Quick Reference

```python
CHANNEL_NICHE = <random>         # Randomly picks each run from: AI & Tech | Finance | Business | Health | History | English Learning | Legal & Tax | Senior Health | Soundscapes
                                 # Override with env var CHANNEL_NICHE="Finance" to force a specific niche
SCRIPT_WORD_COUNT = 1100         # ~8 min — mid-roll eligible
VIDEO_BACKGROUND_MODE            # "ai_images" (default) or "pexels"
VIDEO_ANIMATION_MODE             # "ken_burns" (default, free) or "veo" (GCP, $0.80/video)
MUSIC_ENABLED                    # "true" (default) — CC0 only
LANGUAGE = "en"                  # "en", "hi", "es"
VIDEO_FORMAT = "landscape"       # "landscape" (1920×1080) or "shorts" (1080×1920)
COMMENTS_ENABLED = false         # YouTube comment topic research
PLAYLIST_ENABLED = true          # Auto-group into playlists
APPROVAL_REQUIRED = false        # Manual script approval before render
```

---

## Video Modes

| Mode | Cost | How |
|---|---|---|
| **ken_burns** (default) | FREE | Pollinations AI images + FFmpeg zoompan (17 presets) |
| **veo** | $0.80/video | GCP Vertex AI Veo 3.1 (credits expire July 2026) |

Fallback chain: Ken Burns → Pexels clips → Gradient background

---

## Orchestrator Modes

```bash
python orchestrator.py --mode auto             # New video (default)
python orchestrator.py --mode shorts_from_existing --pick_strategy STRATEGY
# Strategies: recent_high_views, all_time_best, underutilized
```

---

## Crontab (Ubuntu Server)

7 daily jobs: 1 new video + 6 Shorts from existing. All UTC times.
```bash
0 4 * * *   # New video (auto mode)
0 2,8,14,16,18,20 * * *  # 6 Shorts (various strategies)
```
Logs: `/home/harshdeepsingh/cron_logs/`
Always use `/bin/bash -c '...'` and escape `\%Y\%m\%d`.

---

## WhatsApp Approval Queue

When `APPROVAL_REQUIRED=true`:
1. Script saved to Supabase → WhatsApp notification sent
2. Reply `1` (approve), `2` (reject), `3` (view details)
3. Auto-approves after 6h if no response
4. Webhook: `uvicorn webhook_server:app --port 8765` + Cloudflare tunnel

---

## GitHub Actions

**Status:** Pipeline being re-enabled (2026-05-16) now that render is fast enough.
- 2,000 free min/month (private) or unlimited (public repo)
- Runner: 2 CPU, 7 GB RAM, 14 GB disk — matches our VM specs
- At ~4 min/job: fits ~100 videos/month in free tier

**Secrets needed:** `ANTHROPIC_API_KEY`, `YOUTUBE_TOKEN_JSON`, `YOUTUBE_CLIENT_SECRETS`, `PEXELS_API_KEY`

---

## Common Pitfalls

- **`google-generativeai` import** → wrong package; use `google-genai`
- **`python` not found on Mac** → use `.venv/bin/python3`
- **Pexels returns AI robot clips** → `visual_queries` should be cinematic, not topic-literal
- **Video too long** → `SCRIPT_WORD_COUNT` in config.py
- **Font not found** → add path to `_load_fonts()` candidates list
- **Music files with only album art** → `_get_music_path()` validates audio stream exists
- **FFmpeg concat fails** → ensure all segments use identical codec/resolution/fps/pix_fmt
- **Cron syntax on Ubuntu** → `/bin/bash -c`, escape `\%Y\%m\%d`
- **Audio "Failed to find MPEG frames"** → pyttsx3 fallback must FFmpeg-convert WAV→MP3 (not rename). Fixed in voice_agent.py.
- **Portrait videos from general pipeline** → `_ffmpeg_final_composite()` enforces `-s {W}x{H}`. Never remove it.
- **Kling/Pika/Seedance code** → ARCHIVED. Methods are no-op stubs. Do NOT re-add imports from `agents.kling_video_agent`.

---

## Architecture Decisions (2026-05-19)

- **Voice fallback chain:** edge-tts (retries up to 3 voices from niche pool) → pyttsx3 + FFmpeg WAV→MP3 conversion. Never rename WAV to .mp3 — always convert.
- **Video resolution enforcement:** Final composite FFmpeg command includes explicit `-s {W}x{H}` flag. Shorts conversion uses single-pass FFmpeg with `scale+pad` filter (no MoviePy for resize).
- **Niche rotation:** `CHANNEL_NICHE` randomly selected each run (env var override available). All downstream agents (voice, research, colors, thumbnails) auto-adapt.
- **Disk cleanup:** Pre-flight check — if <2GB free, aggressively clears ALL outputs + cache before render. Normal cleanup: cache >500MB gets cleared, output dirs >6h old deleted.
- **Dead code policy:** Kling/Pika/Seedance/Replicate methods are no-op stubs returning `{}`. Do NOT add real imports — the modules don't exist.

---

## Archived Features

See `KLING_ARCHIVE.md` for removed integrations (Kling, Seedance, LeiaPix, Pika).
All replaced by free Ken Burns or GCP Veo.

---

## MCP Tools: code-review-graph

**Use graph tools BEFORE Grep/Glob/Read for code exploration.**

Key tools: `detect_changes`, `get_impact_radius`, `get_affected_flows`, `query_graph`, `semantic_search_nodes`, `get_architecture_overview`

The graph auto-updates on file changes via hooks.
