# AutoTube

Fully autonomous faceless YouTube channel — local execution with GCP/Veo integration, costs ~$0-3/month.

AutoTube automatically researches trending topics, writes scripts with AI (Claude/Gemini/Groq 3-way fallback), synthesizes voiceovers, renders cinematic videos, creates thumbnails, and uploads to YouTube — with zero human involvement after initial setup. Supports multi-language (English, Hindi, Spanish), YouTube Shorts, and mid-roll ad-optimized 8+ minute videos.

---

## How It Works

```
Research → Script → Voiceover → Video → Thumbnail → Upload → Analytics
   ↓           ↓         ↓          ↓         ↓          ↓         ↓
pytrends    Claude    edge-tts   Pexels    Pillow    YouTube   Feedback
Reddit      Gemini    (free,     Ken Burns  AI-gen   API v3    Loop
RSS feeds   Groq      multi-     or Veo    backgrounds OAuth2   (v4)
Comments   (fallback) language)
```

Each video (v4):
- **8+ minutes** long (~1100 words at 150 wpm) — mid-roll ad eligible for 2-3x RPM
- **8 unique visual sections** — cinematic AI backgrounds or Pexels B-roll
- **Voice variety** — random selection from niche-specific voice pools
- **CC0 background music** — auto-fetched from Pixabay (zero copyright risk)
- **Bold opening title card** — large text with accent word
- **Subtitle-style captions** at bottom throughout
- **Multi-language** — English, Hindi, Spanish with native TTS voices

---

## Features

| Feature | Description | Status |
|---------|-------------|--------|
| Mid-Roll Ads | 8+ min videos (1100 words, 8 sections) for 2-3x RPM | v4 Default |
| Voice Variety | Random niche-specific voice pools (no "bot channel" flags) | v4 Default |
| CC0 Music | Auto-fetch royalty-free Pixabay tracks | v4 `MUSIC_ENABLED=true` |
| Multi-Language | Hindi (`LANGUAGE=hi`) and Spanish (`LANGUAGE=es`) | v4 |
| Analytics Loop | YouTube Analytics → topic scoring boost | v4 (requires scope) |
| Approval Queue | Manual script review before rendering | v4 `APPROVAL_REQUIRED=true` |
| 9 Niches | AI & Tech, Finance, Business, Health, History, English Learning, Legal & Tax, Senior Health, Soundscapes | v4 |
| Shorts (9:16) | Vertical videos for YouTube Shorts | v3 `VIDEO_FORMAT=shorts` |
| YouTube Comments | Audience-driven topic research | v3 `COMMENTS_ENABLED=true` |
| Auto-Playlists | Auto-group videos by keyword | v3 Default |
| Ken Burns | Free FFmpeg zoom/pan animations | Default |
| GCP Veo 3.1 | Native AI video generation | `VIDEO_ANIMATION_MODE=veo` |
| 3-Way LLM Fallback | Claude → Gemini → Groq | Default |
| GCS Backup | Auto-backup failed uploads to GCS + retry | Default |

---

## Daily Schedule

| Trigger | Type | UTC Time | Videos/run |
|---------|------|----------|------------|
| New Video | Landscape (8+ min) | 04:00 | 1 |
| Shorts #1 | From existing (trending) | 02:00 | 1 |
| Shorts #2 | From existing (top performer) | 08:00 | 1 |
| Shorts #3 | From existing (revival) | 14:00 | 1 |
| Shorts #4 | From existing (revival) | 16:00 | 1 |
| Shorts #5 | From existing (evergreen) | 18:00 | 1 |
| Shorts #6 | From existing (viral) | 20:00 | 1 |

**Total: 7 videos/day (1 new + 6 Shorts), fully automated. Monthly cost: ~$1-3.**

---

## Quick Start (Local Setup)

### Prerequisites
- Python 3.11+
- `ffmpeg` installed (`brew install ffmpeg` on Mac)
- API keys (at least one LLM provider):
  - Anthropic API key (console.anthropic.com) — primary
  - Gemini API key (ai.google.dev) — fallback
  - Groq API key (console.groq.com) — ultimate fallback
- Pexels API key (pexels.com/api) — free
- Google Cloud project with YouTube Data API v3 enabled

### 1. Install dependencies
```bash
cd autotube
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API keys
```bash
python setup.py
# Enter: ANTHROPIC_API_KEY, PEXELS_API_KEY
# Optional: GEMINI_API_KEY, GROQ_API_KEY (for 3-way fallback)
```

### 3. Authorize YouTube (one-time)
```bash
python setup.py --auth
# Browser opens → log in → approve access
# Token saved to data/youtube_token.json

# For analytics feedback loop (optional, v4):
# Regenerate token with yt-analytics.readonly scope
```

### 4. Test locally (no upload)
```bash
# English (default, 8+ min mid-roll eligible)
./run_local.sh --topic "Artificial Intelligence in 2025"

# Hindi
./run_hindi.sh --dry-run --topic "AI Tools"

# Spanish
./run_spanish.sh --dry-run --topic "AI Tools"

# Shorts (9:16 vertical)
VIDEO_FORMAT=shorts ./run_local.sh --topic "Quick AI Tip"

# Output: outputs/<run_id>/video.mp4
open outputs/
```

### 5. Live upload test
```bash
./run_local.sh --upload --topic "Artificial Intelligence in 2025"
```

---

## GitHub Actions Setup

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial AutoTube setup"
# Create private repo at github.com/new, then:
git remote add origin https://github.com/YOUR_USERNAME/autotube.git
git push -u origin main
```

### Step 2 — Add GitHub Secrets
Go to: **Settings → Secrets and variables → Actions → Secrets**

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key (`sk-ant-...`) |
| `GEMINI_API_KEY` | Google Gemini key (fallback) |
| `GROQ_API_KEY` | Groq key (ultimate fallback) |
| `YOUTUBE_TOKEN_JSON` | Full contents of `data/youtube_token.json` |
| `YOUTUBE_CLIENT_SECRETS` | Full contents of `client_secrets.json` |
| `PEXELS_API_KEY` | Your Pexels API key |
| `GCP_PROJECT_ID` | Optional — for Veo video generation |
| `GCP_GCS_BUCKET` | Optional — for Veo/GCS backup |
| `AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON` | Optional — GCP service account JSON |

### Step 3 — Add GitHub Variable
Go to: **Settings → Secrets and variables → Actions → Variables**

| Variable name | Value |
|---|---|
| `SCRIPT_MODEL_PROVIDER` | `claude` |

### Step 4 — Done
Pipeline runs automatically 4×/day. Check the **Actions** tab to monitor runs.

---

## Switching AI Provider

Default is `auto` (3-way fallback: Claude → Gemini → Groq). Override via env var:
- `auto` → tries Claude first, falls back to Gemini, then Groq on quota errors
- `claude` → Anthropic Claude Sonnet only
- `gemini` → Google Gemini 2.0 Flash only
- `groq` → Groq (Llama) only

For local testing:
```bash
SCRIPT_MODEL_PROVIDER=gemini ./run_local.sh --topic "AI news"
```

---

## Configuration

Edit `config.py` to customize:

| Field | Default | Description |
|---|---|---|
| `CHANNEL_NICHE` | `"AI & Tech"` | Content niche — affects colors, research, voices, angles |
| `CHANNEL_NAME` | `"AutoTube"` | Shown in watermark overlay |
| `SCRIPT_WORD_COUNT` | `1100` | ~8 min at 150 wpm (mid-roll eligible) |
| `TARGET_VIDEO_SECONDS` | `440` | Target video duration |
| `LANGUAGE` | `"en"` | `en`, `hi` (Hindi), `es` (Spanish) |
| `SCRIPT_MODEL_PROVIDER` | `"auto"` | `auto` (3-way fallback), `claude`, `gemini`, `groq` |
| `VIDEO_FORMAT` | `"landscape"` | `landscape` (1920x1080) or `shorts` (1080x1920) |
| `VIDEO_ANIMATION_MODE` | `"ken_burns"` | `ken_burns` (free) or `veo` (GCP) |
| `MUSIC_ENABLED` | `true` | CC0 background music from Pixabay |
| `APPROVAL_REQUIRED` | `false` | Require manual script approval before render |
| `COMMENTS_ENABLED` | `false` | YouTube comment topic research |
| `PLAYLIST_ENABLED` | `true` | Auto-group videos into playlists |
| `DARK_OVERLAY_OPACITY` | `0.52` | Darkness over footage for caption contrast |

Available niches: `AI & Tech` · `Finance` · `Business` · `Health` · `History` · `English Learning` · `Legal & Tax` · `Senior Health` · `Soundscapes`

---

## Manual Pipeline Trigger

From GitHub Actions tab → **Run workflow**:

| Input | Description |
|---|---|
| `count` | Videos per run (default: 1) |
| `dry_run` | Generate video but skip upload |
| `force_topic` | Override research with a specific topic |
| `model_provider` | `claude` or `gemini` (overrides Variable) |

---

## Cost Breakdown

| Service | Cost |
|---|---|
| Pexels Video API | Free (200 req/hour) |
| Pollinations AI (thumbnails/backgrounds) | Free (no key needed) |
| edge-tts (Microsoft TTS) | Free (100+ voices/languages) |
| Pixabay Music | Free (CC0 license) |
| YouTube Data API | Free (10,000 units/day quota) |
| Anthropic Claude API | ~$0.01–0.03/video |
| Gemini / Groq (fallback) | Free tier available |
| GCP Veo (optional) | ~$0.80/video ($300 free credits) |
| Hosting / server | Local execution or VM |

**Monthly cost: ~$1-3 in LLM credits for 210 videos/month (30 new + 180 Shorts).**

---

## Folder Structure

```
autotube/
├── agents/
│   ├── research_agent.py         # pytrends + Reddit + RSS + Analytics → scored topics
│   ├── script_agent.py           # Claude/Gemini/Groq (3-way fallback) → script JSON
│   ├── voice_agent.py            # edge-tts (multi-voice pools) → audio.mp3
│   ├── video_agent.py            # Pexels/Ken Burns/Veo → video.mp4
│   ├── thumbnail_agent.py        # Pillow + Pollinations AI → thumbnail.jpg
│   ├── upload_agent.py           # YouTube API + playlist management → published
│   ├── music_agent.py            # Pixabay CC0 music auto-fetch (v4)
│   ├── analytics_agent.py        # YouTube Analytics feedback loop (v4)
│   ├── comment_research_agent.py # YouTube comments → topic research
│   ├── gcp_veo_agent.py          # GCP Vertex AI Veo 3.1 → native video
│   ├── gcp_cost_tracker.py       # GCP credit usage monitoring
│   └── gcs_backup_agent.py       # GCS backup for failed uploads
├── templates/
│   └── prompts.py                # LLM prompts (landscape, Shorts, multi-language)
├── data/
│   ├── topics_history.json       # deduplication
│   ├── posted_videos.json        # upload log
│   ├── topic_performance.json    # analytics feedback data (v4)
│   ├── pending_approval.json     # approval queue (v4)
│   ├── playlists.json            # auto-playlist cache
│   ├── upload_status.json        # GCS backup manifest
│   └── music/                    # CC0 background music (auto-downloaded)
├── outputs/
│   └── video_cache/              # cached clips/images (by hash)
├── .github/workflows/
│   └── daily_pipeline.yml        # cron triggers (currently disabled)
├── config.py                     # all settings in one place
├── orchestrator.py               # pipeline entry point
├── review.py                     # manual approval queue CLI (v4)
├── run_local.sh                  # local test runner (English)
├── run_hindi.sh                  # Hindi pipeline runner (v4)
├── run_spanish.sh                # Spanish pipeline runner (v4)
├── setup.py                      # one-time setup wizard
└── V4_PLAN.md                    # strategic plan document
```

---

## Re-authorizing YouTube

If the token expires (unused 6+ months) or you revoke access:
```bash
python setup.py --auth
# Then update the YOUTUBE_TOKEN_JSON secret in GitHub
```

## Verify all credentials
```bash
python setup.py --check
```
