# AutoTube

Fully autonomous faceless YouTube channel — runs on GitHub Actions, costs ~$0/month.

Every day at 4 scheduled times, AutoTube automatically researches trending topics, writes a script with Claude AI, synthesizes a voiceover, renders a cinematic video with Pexels stock footage, creates a thumbnail, and uploads it to YouTube — with zero human involvement after initial setup.

---

## How It Works

```
Research → Script → Voiceover → Video → Thumbnail → Upload
   ↓           ↓         ↓          ↓         ↓          ↓
pytrends    Claude    edge-tts   Pexels    Pillow    YouTube API
Reddit      /Gemini   (free)     B-roll    gradient  OAuth2
RSS feeds
```

Each video:
- **4–5 minutes** long (~650 words at 150 wpm)
- **6 unique Pexels clips** — one per section, cinematic/beautiful footage
- **Bold opening title card** — large text with yellow accent word
- **Subtitle-style captions** at bottom throughout
- **Thin progress bar** at bottom edge

---

## Daily Schedule

| Trigger | IST Time | UTC Time | Videos/run |
|---------|----------|----------|------------|
| Run 1   | 09:00    | 03:30    | 1          |
| Run 2   | 12:00    | 06:30    | 1          |
| Run 3   | 15:00    | 09:30    | 1          |
| Run 4   | 18:00    | 12:30    | 1          |

**Total: 4 videos/day, fully automated. Monthly cost: ~$0.**

---

## Quick Start (Local Setup)

### Prerequisites
- Python 3.11+
- `ffmpeg` installed (`brew install ffmpeg` on Mac)
- Anthropic API key (console.anthropic.com)
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
```

### 3. Authorize YouTube (one-time)
```bash
python setup.py --auth
# Browser opens → log in → approve access
# Token saved to data/youtube_token.json
```

### 4. Test locally (no upload)
```bash
./run_local.sh --topic "Artificial Intelligence in 2025"
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
| `YOUTUBE_TOKEN_JSON` | Full contents of `data/youtube_token.json` |
| `YOUTUBE_CLIENT_SECRETS` | Full contents of `client_secrets.json` |
| `PEXELS_API_KEY` | Your Pexels API key |
| `GEMINI_API_KEY` | Optional — only if switching to Gemini |

### Step 3 — Add GitHub Variable
Go to: **Settings → Secrets and variables → Actions → Variables**

| Variable name | Value |
|---|---|
| `SCRIPT_MODEL_PROVIDER` | `claude` |

### Step 4 — Done
Pipeline runs automatically 4×/day. Check the **Actions** tab to monitor runs.

---

## Switching AI Provider

Change `SCRIPT_MODEL_PROVIDER` in GitHub Variables (no code push needed):
- `claude` → uses Anthropic Claude Sonnet (default)
- `gemini` → uses Google Gemini 2.0 Flash

For local testing:
```bash
SCRIPT_MODEL_PROVIDER=gemini ./run_local.sh --topic "AI news"
```

---

## Configuration

Edit `config.py` to customize:

| Field | Default | Description |
|---|---|---|
| `CHANNEL_NICHE` | `"AI & Tech"` | Content niche — affects colors and research topics |
| `CHANNEL_NAME` | `"AutoTube"` | Shown in watermark overlay |
| `SCRIPT_WORD_COUNT` | `650` | ~4.5 min at 150 wpm |
| `UPLOAD_TIMES_IST` | `["09:00","12:00","15:00","18:00"]` | Upload slots (IST, auto-converts to UTC) |
| `TTS_VOICE` | `"en-US-GuyNeural"` | edge-tts voice |
| `DARK_OVERLAY_OPACITY` | `0.52` | Darkness over footage for caption contrast |
| `CAPTION_FONT_SIZE` | `52` | Caption text size in pixels |

Available niches: `AI & Tech` · `Finance` · `Business` · `Health` · `History`

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
| GitHub Actions | Free (uses ~80 of 2,000 free min/month) |
| Pexels Video API | Free (200 req/hour) |
| edge-tts (Microsoft TTS) | Free |
| YouTube Data API | Free (10,000 units/day quota) |
| Anthropic Claude API | ~$0.01–0.03/video |
| Hosting / server | $0 — GitHub IS the infrastructure |

**Monthly cost: ~$1–3 in Claude API credits for 120 videos/month.**

---

## Folder Structure

```
autotube/
├── agents/
│   ├── research_agent.py    # pytrends + Reddit + RSS → trending topics
│   ├── script_agent.py      # Claude/Gemini → structured script JSON
│   ├── voice_agent.py       # edge-tts → audio.mp3
│   ├── video_agent.py       # Pexels B-roll + captions → video.mp4
│   ├── thumbnail_agent.py   # Pillow → thumbnail.jpg
│   └── upload_agent.py      # YouTube Data API → published video
├── templates/
│   └── prompts.py           # Claude/Gemini prompt templates
├── data/
│   ├── topics_history.json  # deduplication — committed back by Actions
│   ├── posted_videos.json   # upload log — committed back by Actions
│   └── music/               # optional background music (.mp3/.wav)
├── outputs/
│   └── video_cache/         # cached Pexels clips (avoids re-download)
├── .github/workflows/
│   └── daily_pipeline.yml   # 4 cron triggers at IST 09/12/15/18:00
├── config.py                # all settings in one place
├── orchestrator.py          # pipeline entry point
├── setup.py                 # one-time setup wizard
└── run_local.sh             # local test runner
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
