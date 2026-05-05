# AutoTube — Claude Code Instructions

Autonomous faceless YouTube channel pipeline. Local GCP/Veo implementation. GitHub Actions pipeline currently disabled (2026-04-28) — using local execution instead.

---

## Git Workflow — IMPORTANT

**Never run `git add`, `git commit`, or `git push` without explicit instruction from the user.**

After completing code changes, tell the user:
- Which files were changed and what was changed
- That they should review with `git diff` before committing
- Suggest a commit message, but let them run the command

The user reviews all changes before committing. Do not automate git operations.

---

## What's New (2026-05-05)

### Three Major Features Added

| Feature | What | How to Enable | Result |
|---------|------|---------------|--------|
| **Shorts (9:16)** | Generate vertical videos for YouTube Shorts | `VIDEO_FORMAT=shorts` | Portrait 1080×1920 videos, 150-word scripts |
| **YouTube Comments** | Research topics from audience comments | `COMMENTS_ENABLED=true` | Audience-driven topic research + Reddit + pytrends |
| **Auto-Playlists** | Auto-group videos into keyword playlists | `PLAYLIST_ENABLED=true` (default) | All videos organized by topic, no manual work |

### New Orchestrator Mode
```bash
# Generate Shorts from existing videos (6 daily crons)
python orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views
# Strategies: recent_high_views, all_time_best, underutilized
```

### Quick Start
```bash
# Test all three features
VIDEO_FORMAT=shorts COMMENTS_ENABLED=true PLAYLIST_ENABLED=true \
  python orchestrator.py --dry-run --count 1 --topic "AI Tools"

# Test Shorts from existing videos
python orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views --dry-run
```

See sections below for detailed setup, testing, and crontab configuration.

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
| `agents/research_agent.py` | pytrends + Reddit + RSS + YouTube comments → scored topic list |
| `agents/script_agent.py` | Claude or Gemini → structured script JSON |
| `agents/voice_agent.py` | edge-tts (primary) + pyttsx3 (fallback) → audio.mp3 |
| `agents/video_agent.py` | Pexels B-roll + Pillow captions → MP4 (landscape 1920×1080 or Shorts 1080×1920) |
| `agents/gcp_veo_agent.py` | GCP Vertex AI Veo 3.1 → text-to-video (Phase 2) |
| `agents/gcp_cost_tracker.py` | GCP credit usage monitoring vs $300 budget |
| `agents/thumbnail_agent.py` | Pillow → JPEG thumbnail (landscape 1280×720 or Shorts 1080×1920) |
| `agents/upload_agent.py` | YouTube Data API v3, OAuth2, resumable upload, playlist management |
| `agents/comment_research_agent.py` | YouTube comments → audience-driven topic research |
| `templates/prompts.py` | All LLM prompt templates — landscape, Shorts, and YouTube comment guidance |
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

### Basic Settings
```python
CHANNEL_NICHE = "AI & Tech"      # Options: AI & Tech | Finance | Business | Health | History | English Learning
                                  # Changing niche auto-switches: subreddits, RSS feeds, accent colors, script angle guidance
CHANNEL_NAME = "AutoTube"        # shown in top-left watermark
SCRIPT_WORD_COUNT = 650          # ~4.5 min — don't increase beyond 800
SCRIPT_MODEL_PROVIDER            # "claude" or "gemini" — set via env var
VIDEO_BACKGROUND_MODE            # "ai_images" (V2, default) or "pexels" (V1) — set via env var / GitHub Variable
VIDEO_ANIMATION_MODE             # "ken_burns" (default), "veo" — switch via env var
MUSIC_ENABLED                    # "true" (default) or "false" — IMPORTANT: only use CC0 music, YouTube deducts 55% for licensed music
DARK_OVERLAY_OPACITY = 0.52      # how dark the footage overlay is (0.4–0.65)
PEXELS_CLIPS_PER_VIDEO = 6       # Dynamic: matches actual section count (4-8 based on script complexity)
```

### Feature 1: Multi-Format Videos (NEW 2026-05-05)
```python
VIDEO_FORMAT = "landscape"       # "landscape" (default, 1920×1080) or "shorts" (9:16, 1080×1920)
                                  # Set: VIDEO_FORMAT=shorts python orchestrator.py --dry-run
VIDEO_WIDTH = 1920 / 1080        # Auto-set based on VIDEO_FORMAT (computed field)
VIDEO_HEIGHT = 1080 / 1920       # Auto-set based on VIDEO_FORMAT (computed field)
THUMB_WIDTH = 1280 / 1080        # Auto-set based on VIDEO_FORMAT (computed field)
THUMB_HEIGHT = 720 / 1920        # Auto-set based on VIDEO_FORMAT (computed field)
SHORTS_WORD_COUNT = 150          # 150 words for 9:16 Shorts (vs 650 for landscape)
# IS_SHORTS property                # config.IS_SHORTS returns True if VIDEO_FORMAT=="shorts"
```

**Testing Shorts:**
```bash
# Generate a Shorts video (9:16 vertical for YouTube Shorts / TikTok)
VIDEO_FORMAT=shorts python orchestrator.py --dry-run --count 1 --topic "Test Topic"
# Output: 1080×1920 MP4, ~150-word script, #Shorts tags
```

### Feature 2: Audience-Driven Topics via YouTube Comments (NEW 2026-05-05)
```python
COMMENTS_ENABLED = false         # Enable YouTube comment topic research
COMMENTS_OWN_VIDEOS = 10         # Number of your own videos to extract comments from
COMMENTS_COMPETITOR_VIDEOS = 5   # Number of competitor videos to scan
COMMENTS_MAX_PER_VIDEO = 100     # Max comments to fetch per video
```

**How it works:**
- Extracts topic ideas from your channel's video comments
- Also scans competitor videos in your niche for audience demands
- Identifies questions, feature requests, and video suggestions
- Merges with Reddit + pytrends + RSS sources before scoring

**Testing Comments:**
```bash
# Enable comment research
COMMENTS_ENABLED=true python orchestrator.py --dry-run --count 1 --topic "Test"
# Check logs for: "YouTube Comments: N topics extracted"
```

**Requirements:**
- YouTube OAuth2 token with `youtube` scope (auto-handled by `generate_youtube_token.py`)
- Channel must have uploaded videos
- Graceful fallback: if auth missing, skips comments without crashing

### Feature 3: Auto-Playlist Grouping (NEW 2026-05-05, ENABLED BY DEFAULT)
```python
PLAYLIST_ENABLED = true          # Auto-group videos into keyword-based playlists (now DEFAULT)
                                  # Set: PLAYLIST_ENABLED=false to disable (still supported)
PLAYLIST_AUTO_CREATE = true      # Create new playlists automatically if keyword not found
PLAYLIST_MAP = {}                # Static keyword→playlist_id overrides (optional)
                                  # Example: PLAYLIST_MAP_JSON='{"AI": "PLxxx123", "Python": "PLyyy456"}'
# data/playlists.json             # Persists auto-created playlist IDs across runs (auto-managed)
```

**How it works:**
- After uploading a video, derives a keyword from video tags or channel niche
- Looks for existing playlist matching keyword (4-step resolution):
  1. Check static PLAYLIST_MAP overrides
  2. Check persisted playlists.json cache
  3. Query YouTube for existing playlist by title
  4. Auto-create new playlist if none found
- Inserts video into resolved playlist

**Testing Playlists:**
```bash
# Playlists enabled by default; test that tagging works
PLAYLIST_ENABLED=true python orchestrator.py --dry-run --count 1 --topic "AI Tools"
# Check logs for: "Playlist resolved: X" or "Created playlist: X"
```

**Why PLAYLIST_ENABLED defaults to true:**
- Auto-organizing 7 uploads/day (1 new + 6 Shorts) requires playlist structure
- Better YouTube algorithm performance (organized playlists boost channel authority)
- Improved viewer retention (subscribers can binge by topic)
- Zero manual work (fully automated)

---

**VIDEO_ANIMATION_MODE options:**
- `ken_burns` — Free, FFmpeg zoom/pan (default, no API setup)
- `veo` — GCP Vertex AI Veo 3.1 native video (requires GCP setup + $300 credits)

---

## Video Animation Modes

**Default (Recommended):** Ken Burns — completely free, no API setup needed

| Mode | Approach | Cost | Speed | Quality | Fallback |
|---|---|---|---|---|---|
| **ken_burns** (default ✓) | Pollinations AI images + FFmpeg zoom/pan | FREE | 1-2 min | Good | Always available |
| **veo** (production) | GCP Vertex AI native video | $0.80/video | 2-4 min | Excellent | Falls back to Ken Burns |

**Fallback Chain (always free):**
`Ken Burns → Pexels clips → Gradient background`

**To use Veo (requires GCP setup):**
```bash
# Set in .env or GitHub Variable
VIDEO_ANIMATION_MODE=veo
GCP_PROJECT_ID=your-project-id
GCP_GCS_BUCKET=autotube-veo-output
AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON={...service account JSON...}
```

**How to switch modes (local testing):**
```bash
VIDEO_ANIMATION_MODE=ken_burns python orchestrator.py --dry-run --topic "Test"
VIDEO_ANIMATION_MODE=veo python orchestrator.py --dry-run --topic "Test"
```

**Ken Burns** (current default): Uses FFmpeg zoompan with 17 animation presets (zoom, pan, drift effects). Completely free, no API setup needed, fastest option.

**Veo**: Generates native 1080p videos directly from visual_queries using GCP Vertex AI. Highest quality, but requires GCP credits (~$0.80 per video).

**Caching**: Videos cache by hash in `outputs/video_cache/` (prefixed `fx_*` for Ken Burns, `veo_*` for Veo). Fallback chain attempts Ken Burns if primary mode fails.

**Fallback chain**: If active mode fails (API down, quota hit, network error) → gracefully falls back to gradient background for that section. Video continues playing with text overlays.

---

## Shorts from Existing Videos — Daily Automation (NEW 2026-05-05)

**Purpose:** Repurpose your 38+ existing videos as 9:16 Shorts for YouTube Shorts platform. Generate 6 Shorts/day from intelligent video rotation strategies.

### Orchestrator Mode
```bash
# New mode in orchestrator.py
python orchestrator.py --mode shorts_from_existing --pick_strategy STRATEGY [--batch N] [--dry-run]
```

### Pick Strategies

| Strategy | What It Does | When to Use |
|----------|-------------|------------|
| `recent_high_views` | Top video from last 7 days | Daily (trending content) |
| `all_time_best` | Highest-viewed video overall | Weekly (evergreen content) |
| `underutilized` | Low-view videos needing revival | Multi-times/week (revive old content) |
| `manual` | Specific video by ID override | Ad-hoc testing |

### Testing Shorts from Existing
```bash
# Test mode (no upload)
python orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views --dry-run

# Live mode (actually uploads)
python orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best
```

### Crontab Setup for Ubuntu Server

Create/edit crontab with 6 daily Shorts crons:

```bash
# All times in UTC — Convert to your timezone (IST = UTC + 5:30)

# Shorts #1: 02:00 UTC — Recent high-views (last 7 days, trending)
0 2 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views >> /home/harshdeepsingh/cron_logs/autotube_shorts_recent_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'

# Shorts #2: 08:00 UTC — All-time best (top performer)
0 8 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best >> /home/harshdeepsingh/cron_logs/autotube_shorts_best_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'

# Shorts #3: 14:00 UTC — Underutilized #1 (low-view revival)
0 14 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy underutilized >> /home/harshdeepsingh/cron_logs/autotube_shorts_underutilized_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'

# Shorts #4: 16:00 UTC — Underutilized #2 (another low-view revival)
0 16 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy underutilized >> /home/harshdeepsingh/cron_logs/autotube_shorts_underutil2_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'

# Shorts #5: 18:00 UTC — Evergreen (highest-viewed, rotates weekly)
0 18 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best >> /home/harshdeepsingh/cron_logs/autotube_shorts_evergreen_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'

# Shorts #6: 20:00 UTC — Recent viral (hottest from last 3 days)
0 20 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views >> /home/harshdeepsingh/cron_logs/autotube_shorts_viral_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'

# New Video Pipeline: 04:00 UTC (after prefetch, full pipeline)
0 4 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode auto >> /home/harshdeepsingh/cron_logs/autotube_new_video_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'
```

**To apply to your Ubuntu server:**
```bash
# SSH into server
ssh harshdeepsingh@your-server

# Edit crontab
crontab -e

# Paste the 6 Shorts crons above (replace old broken entries)
# Save and exit

# Verify
crontab -l
```

### Important Crontab Notes

- **Log directory must exist:**
  ```bash
  mkdir -p /home/harshdeepsingh/cron_logs
  ```

- **Virtual env must be activated:**
  ```bash
  . .venv/bin/activate
  ```

- **Bash syntax required:**
  - Use `/bin/bash -c 'command'` (not /bin/sh)
  - Escape date format: `\%Y\%m\%d` (backslash-percent)
  - Syntax: `$(date +\%Y\%m\%d_\%H\%M\%S)` inside quotes

- **Time zones:**
  - All times above are **UTC**
  - Convert to your timezone: IST = UTC + 5:30
  - Example: 02:00 UTC = 07:30 IST

### Monitoring Crons
```bash
# Watch logs in real-time
tail -f /home/harshdeepsingh/cron_logs/autotube_shorts_*.log

# Check which cron just ran
ls -lht /home/harshdeepsingh/cron_logs/ | head -5

# Check running processes
pgrep -af orchestrator.py

# Check system load (if a cron is processing)
top
```

### Result
- **6 Shorts/day × 365 days = 2,190 Shorts/year**
- Repurposing 38 existing videos through intelligent rotation
- Zero additional research/scripting cost (uses existing videos)
- Cost: Free (local processing, no API calls for this mode)

---

## Testing All Three New Features

### Feature 1: Shorts (9:16 Vertical Format)
```bash
# Test Shorts generation locally
VIDEO_FORMAT=shorts python orchestrator.py --dry-run --count 1 --topic "AI Tools"

# Verify output:
# - Video dimensions: 1080×1920 (run: ffprobe outputs/.../video.mp4)
# - Script length: ~150 words
# - Thumbnail: 1080×1920
# - Tags include: #Shorts
```

### Feature 2: YouTube Comments Research
```bash
# Test comment topic extraction
COMMENTS_ENABLED=true python orchestrator.py --dry-run --count 1 --topic "Test"

# Verify in logs:
# ✓ "YouTube Comments: N topics extracted"
# ✓ "data/topics_history.json" has entries with source:"youtube_comments"
# If auth missing: gracefully skips (expected behavior, no error)
```

### Feature 3: Auto-Playlists
```bash
# Test playlist grouping
PLAYLIST_ENABLED=true python orchestrator.py --dry-run --count 1 --topic "AI Tools"

# Verify in logs:
# ✓ "Playlist resolved: AI Tools" or "Created playlist: AI Tools"
# ✓ "data/playlists.json" contains new keyword→id mappings
# Non-blocking: video succeeds even if playlist insert fails
```

### All Three Features Together
```bash
# Test all new features simultaneously
VIDEO_FORMAT=shorts COMMENTS_ENABLED=true PLAYLIST_ENABLED=true \
  python orchestrator.py --dry-run --count 1 --topic "Artificial Intelligence 2025"

# Expected:
# - 1080×1920 Shorts video generated
# - Topics include YouTube comment suggestions
# - Video tagged and grouped into AI playlist
# - All features run without conflicts
```

### Shorts from Existing Videos
```bash
# Test shorts generation from existing videos
python orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views --dry-run

# Expected:
# - Selects 1 video from data/posted_videos.json
# - Re-encodes to 1080×1920 Shorts format
# - Prepares upload (no actual upload in dry-run)
```

### Checking Test Results
```bash
# View generated outputs
ls -lh outputs/

# Check most recent video
ls -lht outputs/ | head -5

# Inspect video properties
ffprobe outputs/latest_id/video.mp4 | grep -i "duration\|width\|height"

# Check topics and playlists
cat data/topics_history.json | tail -20
cat data/playlists.json
```

---

## Feature Architecture & Hooks

All three features use a **hook-based architecture** to avoid merge conflicts:

### Research Hook: `_extra_sources()` in `research_agent.py`
```python
# research_agent.py:get_topics()
if config.COMMENTS_ENABLED:
    topics.extend(comment_agent.get_comment_topics(...))
```
**Result:** YouTube comments merge with Reddit + pytrends + RSS topics

### Upload Hook: `_post_upload()` in `upload_agent.py`
```python
# upload_agent.py:publish()
if config.PLAYLIST_ENABLED:
    self._add_to_playlist(video_id, script)
```
**Result:** Videos auto-grouped into keyword-based playlists

### Script Hook: Conditional prompt in `script_agent.py`
```python
# script_agent.py:generate()
if config.IS_SHORTS:
    prompt = SHORTS_USER_PROMPT  # 150 words, 3 sections
else:
    prompt = SCRIPT_USER_PROMPT  # 650 words, 6+ sections
```
**Result:** Appropriate script length and structure for format

---

## GCP Veo 3.1 — Text-to-Video Generation (Phase 2)

**NEW (2026-04-22):** Google Vertex AI Veo 3.1 integration for high-quality native video generation.

### What is Veo?
- **Text-to-video** generation via Google Cloud Vertex AI API
- **Quality:** Native video, cinematic quality (8-second 1080p)
- **Speed:** 2-4 minutes per video (async polling)
- **Cost:** $0.10/sec → ~$0.80 per 8-sec video
- **Budget:** $300 free trial (Phase 2 uses GCP free credits)

### How to Enable Veo
Set in `.env` or GitHub Variable:
```bash
VIDEO_ANIMATION_MODE=veo
```

This switches `video_agent.py` to Veo-only mode (no fallback to Ken Burns unless Veo fails).

### Required GCP Setup
1. Create GCP project (if not done)
2. Enable **Vertex AI API** (`aiplatform.googleapis.com`)
3. Enable **Cloud Storage API** (`storage.googleapis.com`)
4. Create **GCS bucket** (e.g., `autotube-veo-output`)
5. Create **service account** with roles:
   - `Vertex AI User` (for Veo generation)
   - `Storage Object Creator` + `Storage Object Viewer` (for GCS read/write)
6. Download service account JSON key
7. Set `.env` variables:
   ```bash
   GCP_PROJECT_ID=your-project-id
   GCP_GCS_BUCKET=autotube-veo-output
   AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON={...full JSON...}
   ```

### Visual Queries Requirements (CRITICAL)
Veo fails silently on vague or abstract visual queries. Rules:

**✅ DO:**
- Concrete subjects: `"solar farm aerial"`, `"robot arm assembly"`, `"circuit board macro"`
- Specific lighting: `"blue neon glow"`, `"golden hour backlight"`, `"orange dramatic lighting"`
- Picture-able: `"holographic display blue glow"` (people can visualize it)

**❌ DON'T:**
- Generic roles: `"corporate worker"`, `"employee"` ← too vague
- Abstract moods: `"dark moody"`, `"cinematic"` ← undefined
- Abstract concepts: `"data visualization neon glow"` ← what does this look like?

**Example (good):**
```
"quantum computer processor glowing orange dramatic lighting"
"solar panel installation rooftop bright sunlight reflection"
"holographic energy grid map blue neon glow"
```

The improved prompt (`templates/prompts.py`) now enforces these rules. Claude generates high-quality queries automatically.

### How Veo Integration Works
1. **Video Agent** calls `VeoVideoGenerator.generate(visual_query, section_idx, duration=8)`
2. **VeoAPIClient** submits to Vertex AI API (async operation)
3. **Polling loop** checks every 20s until `operation.done == True`
4. **Download** from GCS bucket to local cache
5. **Fallback chain:** If Veo returns empty response:
   - Retry up to 2 more times (3 attempts total)
   - If still empty after 3 retries → gradient background fallback
6. **Caching** by MD5 hash: `outputs/video_cache/gcp_veo/veo_*.mp4`

### Cost Tracking
`agents/gcp_cost_tracker.py` monitors spending:
```python
tracker = GCPCostTracker(initial_credits=300.0)
tracker.log_veo_generation(duration_seconds=8)  # logs $0.80
print(tracker.summary())  # {spent: $0.80, remaining: $299.20, ...}
```

**Budget Alert:** Set $250 threshold in GCP Console to avoid surprise overages.

### Troubleshooting Veo Failures
| Error | Cause | Fix |
|-------|-------|-----|
| `403 Forbidden` on GCS download | Service account lacks Storage permission | Add `Storage Object Viewer` role |
| `No videos in response` | Veo API returned empty | Improved prompt fixes this; retry logic auto-retries |
| `SERVICE_DISABLED` | Vertex AI API not enabled | Enable in GCP Console → APIs & Services |
| `Permission denied: aiplatform.user` | Service account lacks Vertex AI role | Add `Vertex AI User` role |

### Dynamic Sections (2026-04-22)
Veo works with dynamic section counts (4-8 sections based on topic). Script agent generates:
- Variable number of sections
- Matching visual_queries array (one per section)
- Video agent renders all sections

This enables natural video length matching script length (no more forced 6 sections).

---

## GCS Backup & Retry System — Resilient Video Uploads (2026-04-23)

**NEW:** Automatic backup of failed YouTube uploads to Google Cloud Storage with intelligent retry on next pipeline run.

### What It Does
If YouTube upload fails (token expired, network error, quota exceeded, etc.):
1. Video is **automatically backed up to GCS** (`autotube-veo-output` bucket)
2. Upload metadata saved to manifest (`data/upload_status.json`)
3. On **next pipeline run**, videos are automatically retried before generating new ones
4. After successful upload, backup is deleted from GCS

### How It Works

**Files involved:**
- `agents/gcs_backup_agent.py` — GCS upload/download + manifest tracking
- `agents/upload_agent.py` — YouTube upload with GCS fallback
- `orchestrator.py` — Retry pending uploads before rendering new videos
- `data/upload_status.json` — Manifest tracking failed uploads

**Flow:**
```
Video Generated ✓
    ↓
Attempt YouTube Upload
    ├─ Success → Delete backup, done ✅
    └─ Failure → Save to GCS + manifest ⚠️
       
Next Pipeline Run:
    ↓
Check Manifest for Pending Uploads
    ├─ None → Proceed normally ✅
    └─ Found (up to 5) → Retry from GCS
       ├─ Success → Remove from manifest ✅
       └─ Still fails → Increment attempt count ⚠️
```

### Manifest Structure
```json
[
  {
    "gcs_path": "gs://autotube-veo-output/videos/pending/video.mp4",
    "title": "ChatGPT Images 2.0 — The Results Shocked Me",
    "description": "...",
    "tags": ["ChatGPT", "AI"],
    "status": "pending_gcs",  // or "uploaded"
    "attempts": 1,
    "first_backed_up": "2026-04-23T12:34:56.789",
    "last_retry": "2026-04-23T12:34:56.789"
  }
]
```

### Key Features

✅ **No lost videos** — Stored in GCS for as long as needed
✅ **Automatic retry** — Tried again on next run (configurable up to 5 per run)
✅ **Cost-effective** — Videos cost ~$0.02/month to store in GCS
✅ **Audit trail** — Full timestamp + attempt tracking
✅ **Graceful fallback** — Works with existing GCP setup (reuses service account)
✅ **Manifest in git** — Track failures across runs (committed to repo)

### Handling Different Failure Types

| Failure | Cause | Recovery |
|---------|-------|----------|
| `invalid_grant: Token expired` | YouTube OAuth token stale | Auto-retry ✓ |
| `403 Forbidden` | Insufficient permissions | Check token setup |
| `Network timeout` | Temporary network issue | Auto-retry ✓ |
| `Quota exceeded` | YouTube daily limit hit | Retry next day ✓ |
| `Service unavailable` | YouTube API down | Auto-retry ✓ |

### Checking Status

```bash
# View pending uploads
cat data/upload_status.json

# Check GCS bucket (requires gcloud CLI)
gsutil ls gs://autotube-veo-output/videos/pending/

# View manifest in logs
python orchestrator.py --dry-run 2>&1 | grep -i "pending\|gcs"
```

### Troubleshooting

| Issue | Fix |
|-------|-----|
| Videos stuck in GCS | Check `data/upload_status.json` — verify YouTube token is fresh |
| Manifest not updating | Ensure `data/` directory is writable |
| Retry not happening | Check that `_retry_pending_uploads()` runs before new renders |
| GCS backup disabled | Verify `AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON` env var is set |

### Cleanup (if needed)

To manually clear old backups from GCS:
```bash
# View pending videos
gsutil ls gs://autotube-veo-output/videos/pending/

# Delete specific video (replace FILENAME)
gsutil rm gs://autotube-veo-output/videos/pending/FILENAME.mp4

# Or delete old manifests
rm data/upload_status.json
# Will be recreated on next failed upload
```

### Cost Analysis

**GCS storage pricing:** ~$0.02/GB/month (after free tier)

If storing 100 videos (assume 150MB each):
- Total size: ~15GB
- Monthly cost: ~$0.30
- Acceptable for backup reliability

**No additional cost** if videos are uploaded within 30 days (automatic cleanup).

---

## Critical Lesson: Integration Testing Before Commit

**LESSON LEARNED (2026-04-17):** A typo in the Pika API endpoint (`queuee` instead of `queue`) went undetected during implementation and wasn't caught until videos were failing in production. This bug should have been caught immediately.

### Rule: Never commit external API integration code without testing it

Before committing ANY code that makes API calls:
1. **Verify the endpoint URL** against official API documentation — do not assume or copy blindly
2. **Test with a real API call** in dry-run mode — at least one successful request before commit
3. **Check error logs carefully** — typos in URLs are obvious in 404/403 responses
4. **Review URLs character-by-character** — `queue` vs `queuee`, `v1` vs `v2`, typos are easy to miss

### Specific to this codebase:
- **Pika endpoint** (MUST be exact): `https://api.fal.ai/v1/queue/text-to-video` 
  - NOT `queuee` (double-e typo)
  - NOT `v2` or other versions — always check fal.ai docs
- **Pollinations endpoint** (no key required): `https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&nologo=true&model=flux`
- **Supabase endpoints** (from config.SUPABASE_URL): Always use the exact URL from your Supabase project settings

### How to test before commit:
```bash
# For Pika integration:
python orchestrator.py --dry-run --topic "Test Topic" 2>&1 | grep -i "pika\|fal.ai\|error"

# Check for these patterns in logs:
# ✓ "Pika video (via fal.ai) downloaded" = working
# ✗ "403 Client Error" or "404 Client Error" = URL/auth problem
# ✗ "Pika/fal.ai video generation failed" = something is wrong
```

If you see ANY API error in logs before committing, **trace back to the endpoint URL first** — typos are the most common cause.

---

## Common Pitfalls

- **`multiply_volume` AttributeError** — use `MultiplyVolume` effect, not `.multiply_volume()` method
- **`google-generativeai` import** — wrong package; use `google-genai`
- **`python` not found on Mac** — use `.venv/bin/python3` explicitly
- **Pexels returns AI robot clips** — the `visual_queries` field in the script JSON controls this; queries should be cinematic, not topic-literal (e.g. "aerial cityscape" not "artificial intelligence")
- **Video too long** — `SCRIPT_WORD_COUNT` in config.py controls length; 650 = ~4.5 min
- **Font not found** — `video_agent.py` tries multiple system font paths; falls back to PIL default if none found; add your font path to the `candidates` list in `_load_fonts()`
- **Shorts rendering too fast** — `SHORTS_WORD_COUNT=150` auto-sets duration; if video is <30s, increase `SHORTS_WORD_COUNT` or adjust pacing
- **Playlist creation fails silently** — Upload still succeeds (non-blocking); check logs for OAuth permission scope. Ensure `generate_youtube_token.py` was run with `youtube.force-ssl` scope
- **YouTube Comments returning 0 topics** — Requires YouTube OAuth token + uploaded videos on channel. Without auth, gracefully skips (expected). Enable with `COMMENTS_ENABLED=true`
- **Cron syntax errors on Ubuntu** — Always use `/bin/bash -c 'command'` not `/bin/sh`; escape date format with backslash: `$(date +\%Y\%m\%d)` not `$(date+%Y%m%d)`
- **VM runs out of memory during rendering** — 305+ second videos at 1920×1080 need 4-6GB RAM. If you see "Killed" in logs, upgrade VM RAM or add swap file

---

## GitHub Actions

**⚠️ STATUS (2026-04-28):** Scheduled pipeline disabled. Using local GCP implementation instead.

**daily_pipeline.yml:**
- Scheduled runs **DISABLED** (as of 2026-04-28)
- Manual trigger available via Actions tab with `count`, `dry_run`, `force_topic`, `model_provider` inputs
- Each run: 1 video, ~20 min, then commits history files back to repo

**prefetch_pipeline.yml:**
- Runs every 6 hours (if re-enabled)
- Currently optional — not required for daily operations

**Why disabled?** GCP/Veo implementation is working reliably locally. GitHub Actions adds unnecessary CI overhead when local execution is fine.

**To re-enable scheduled runs:**
Uncomment cron triggers in `.github/workflows/daily_pipeline.yml` (lines 4-8):
```yaml
on:
  schedule:
    - cron: '00 23 * * *'   # 23:00 UTC = 05:00 IST
    - cron: '30 5 * * *'    # 05:30 UTC = 11:00 IST
    - cron: '00 11 * * *'   # 13:00 UTC = 17:00 IST
    - cron: '30 17 * * *'   # 17:30 UTC = 23:00 IST
```

**GitHub Variables:**
- `SCRIPT_MODEL_PROVIDER` — `claude` or `gemini` (changeable via UI)
- `VIDEO_BACKGROUND_MODE` — `ai_images` (default) or `pexels`
- `VIDEO_ANIMATION_MODE` — `ken_burns` (default) or `veo`

## Secrets required in GitHub
`ANTHROPIC_API_KEY`, `YOUTUBE_TOKEN_JSON`, `YOUTUBE_CLIENT_SECRETS`, `PEXELS_API_KEY`

**Optional (for Veo video generation):**
- `GCP_PROJECT_ID`
- `GCP_GCS_BUCKET`
- `AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON`

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.

---

## Archived / Removed Features (2026-04-28)

### Kling AI Video Generation — REMOVED

**Status:** Removed from active pipeline (2026-04-28)  
**Reason:** Cost concerns ($0.05-0.10 per video) + reliability issues

**Archive documentation:** See `KLING_ARCHIVE.md` for full integration details if you want to re-enable Kling in the future.

**What was removed:**
- `agents/kling_video_agent.py` — Kling API client
- `agents/kling_quota_manager.py` — Daily quota tracking
- All Kling imports from `video_agent.py`
- Kling fallback modes
- Kling secrets from GitHub workflows

**Why?** Switched to free/cheaper alternatives:
- **Ken Burns** (free, always available)
- **GCP Veo** (higher quality, $0.80/video with $300 free trial)

To re-enable Kling, follow instructions in `KLING_ARCHIVE.md`.

### Seedance (ByteDance) — DEPRECATED

**Status:** Code still present but not recommended  
**Reason:** Requires Replicate API key, less reliable than Veo

If you were using `VIDEO_ANIMATION_MODE=seedance`, switch to:
- `ken_burns` (free default)
- `veo` (better quality, GCP)

### LeiaPix & Pika — REMOVED

**Status:** Removed from active recommendations (2026-04-28)

**Why?**
- LeiaPix: Required OAuth2 client credentials (complex setup)
- Pika: Limited free tier (~25/month), paid option ($0.20/video)

Better alternatives:
- `ken_burns` (free)
- `veo` (high quality, $300 free GCP credits)
