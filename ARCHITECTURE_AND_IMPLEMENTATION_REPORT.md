# AutoTube: Architecture, Implementation & Integration Report

**Status**: Production-Ready  
**Date**: April 19, 2026  
**Repository**: /Users/harshdeepsingh/Projects/git_projects/autotube  
**Primary Use Case**: Automated faceless YouTube video generation (4 videos/day via GitHub Actions)

---

## Executive Summary

AutoTube is a **fully automated video generation pipeline** that creates AI-powered YouTube videos. It runs 4 times daily on GitHub Actions, generating 1 video per run without requiring any server infrastructure.

**Key Metrics:**
- **Runtime per video**: ~20 minutes (dry-run: 5-10 minutes)
- **Cost**: FREE (uses free APIs + $0 Kling credits)
- **Quality**: 1920×1080 MP4 with AI visuals, captions, voice, effects, and music
- **Upload**: Automated to YouTube via OAuth2
- **Reliability**: Multi-fallback architecture (Kling → Ken Burns → Pexels → Gradient)

---

## Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────┐
│  GitHub Actions (Cron: 4x daily)                     │
│  ├─ 09:00 IST (03:30 UTC)                            │
│  ├─ 12:00 IST (06:30 UTC)                            │
│  ├─ 15:00 IST (09:30 UTC)                            │
│  └─ 18:00 IST (12:30 UTC)                            │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  orchestrator.py (Main Pipeline Entry Point)         │
│  └─ Coordinates all agent execution                  │
└─────────────────────────────────────────────────────┘
                        ↓
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
   [Research]      [Script]        [Media]
   [Agent]         [Agent]         [Agents]
        │               │               │
        ↓               ↓               ↓
   Topic with    Script JSON       Voice MP3
   Scores        Metadata          AI Images
                                   B-roll Video
                        ↓
            ┌──────────────────────┐
            │  Video Agent         │
            │  (Video Composition) │
            └──────────────────────┘
                        ↓
            ┌──────────────────────┐
            │  Thumbnail Agent     │
            │  (1280×720 JPEG)     │
            └──────────────────────┘
                        ↓
            ┌──────────────────────┐
            │  Upload Agent        │
            │  (YouTube OAuth2)    │
            └──────────────────────┘
                        ↓
            ✅ Live on YouTube
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.10+ | All agents and orchestration |
| **Package Manager** | pip (requirements.txt) | Dependency management |
| **Task Coordination** | Orchestrator.py (sequential) | Wires agents together |
| **Video Composition** | MoviePy 2.2.1 | MP4 rendering (2.x API, NOT 1.x) |
| **Video Generation** | Kling AI API (primary) | AI cinematic video (~$0/video) |
| **Image Generation** | Pollinations.ai (free) | AI images, no auth required |
| **B-roll Fallback** | Pexels API (free tier) | Stock video clips |
| **Audio (Voice)** | edge-tts (free) | Text-to-speech, 50+ voices |
| **Audio (Music)** | CC0 metadata library | Copyright-free background music |
| **Captions** | Pillow + MoviePy | Burn-in text overlays |
| **LLM (Script)** | Claude API or Gemini | Generate video scripts |
| **Thumbnail** | Pillow | Image manipulation (1280×720) |
| **Upload** | YouTube Data API v3 | OAuth2 resumable upload |
| **Secrets Management** | GitHub Secrets/Variables | API keys, credentials |
| **CI/CD** | GitHub Actions | Scheduling, orchestration |
| **Caching** | Local filesystem | Video/image cache (outputs/video_cache/) |

---

## Core Agents & Responsibilities

### 1. **research_agent.py** - Topic Discovery

**Responsibility**: Find trending YouTube-worthy topics  
**Inputs**: None (autonomous)  
**Outputs**: Ranked topic list with engagement scores  
**APIs Used**:
- **PyTrends**: Google search trends (free)
- **Reddit PRAW**: Subreddit posts, scores
- **RSS Feeds**: Tech blogs, news sites

**Logic**:
```
1. Fetch trending searches (PyTrends)
2. Extract subreddit-relevant posts (PRAW)
3. Score by engagement (upvotes, comments, recency)
4. Return top N topics sorted by relevance
```

**Customization** (via `config.py`):
```python
CHANNEL_NICHE = "AI & Tech"  # Affects subreddit selection, RSS feeds, brand colors
```

---

### 2. **script_agent.py** - Video Script Generation

**Responsibility**: Write structured video scripts from topics  
**Inputs**: Topic string  
**Outputs**: JSON with script structure + visual queries  
**Models Supported**:
- Claude 3.5 Sonnet (via `ANTHROPIC_API_KEY`)
- Gemini 2.0 Flash (via `GEMINI_API_KEY`)

**Output Schema**:
```json
{
  "title": "AI in 2025: 5 Game-Changing Breakthroughs",
  "description": "YouTube description (140 chars)",
  "tags": ["AI", "machine learning", ...],
  "sections": [
    {
      "title": "Introduction",
      "duration_seconds": 30,
      "narrative": "Voice script for this section",
      "visual_query": "Cinematic AI abstract visuals"
    },
    ...
  ],
  "hook_title_text": "AI BREAKTHROUGHS 2025",
  "thumbnail_text": "AI BREAKTHROUGHS"
}
```

**Key Parameters**:
- Word count: `SCRIPT_WORD_COUNT` (default: 650 = ~4.5 min video)
- Model provider: `SCRIPT_MODEL_PROVIDER` env var (`claude` or `gemini`)

**Voice Queries**: The script includes visual suggestions for each 5-section (6 sections × ~90-110 seconds each). Critical for video composition.

---

### 3. **voice_agent.py** - Audio Generation

**Responsibility**: Convert script text to MP3 voice-over  
**Inputs**: Script narrative, speaker voice choice  
**Outputs**: voice.mp3 (mono, 192kbps)  
**Methods**:
1. **Primary**: `edge-tts` (Microsoft Edge TTS)
   - 50+ languages, 100+ voices
   - Free, no auth, low latency
2. **Fallback**: `pyttsx3` (offline synthesis)
   - Robotic, but always available

**Speaker Selection** (based on `CHANNEL_ACCENT` in config):
- US English: `en-US-GuyNeural`
- UK English: `en-GB-RyanNeural`
- Neutral: `en-AU-WilliamNeural`

---

### 4. **video_agent.py** - Video Composition (Core)

**Responsibility**: Stitch images, B-roll, text, music into 1920×1080 MP4  
**Inputs**: Script JSON, voice MP3  
**Outputs**: video.mp4  
**Architecture**:

**A. Image Source (Priority Order)**
```
1. Try Kling AI (cinematic video) — $0 within 66-credit free tier
   - If success: Use generated video clip
   - If quota exhausted: Fall to step 2

2. Ken Burns effect (FFmpeg zoom/pan on static image)
   - Uses Pollinations AI for image
   - 17 animation presets (zoom_in, pan_left, drift, etc.)
   - ~1-2 min per video, completely free

3. Pexels B-roll (stock video clips)
   - Free tier: 1 clip/search
   - Instant (no generation time)
   - Lower visual quality than Kling

4. Gradient background (pure fallback)
   - Never fails, always available
   - Plain color background with text overlay
```

**B. Text Overlay (Captions)**
```
- Burn-in text using Pillow (PIL)
- Font: System font (automatically detected)
- Style: Bold, 48pt, white + black outline
- Position: Bottom third of frame
- Duration: 5 seconds per caption
```

**C. Music Layer**
```
- CC0 (creative commons zero) background music
- Metadata file: config/music_metadata.json
- Mixed to 6% volume (background, not obtrusive)
- Fades in/out with video
- Falls back to silent if file not found
```

**D. Audio Mixing (MoviePy 2.2.1)**
```
1. Load voice MP3
2. Load background music (if available)
3. Lower music volume to 6% via MultiplyVolume effect
4. Composite: voice (main) + music (background)
5. Trim to exact video duration
```

**E. Final Composition**
```
video = VideoFileClip("image.jpg")
video = video.with_duration(duration_seconds)
video = video.with_audio(audio_track)
video = video.resized(new_size=(1920, 1080))
# Add captions
# Add music
# Render to MP4
```

**MoviePy 2.x Critical Notes**:
- NO `.set_duration()` — use `.with_duration()`
- NO `.set_audio()` — use `.with_audio()`
- NO `.resize()` — use `.resized()`
- NO `.subclip()` — use `.subclipped(start, end)`
- Effects: `from moviepy.audio.fx import MultiplyVolume`

---

### 5. **thumbnail_agent.py** - Thumbnail Generation

**Responsibility**: Create 1280×720 JPEG thumbnail for YouTube  
**Inputs**: One key frame image, hook text  
**Outputs**: thumbnail.jpg  
**Process**:
```
1. Load image (from Pollinations or cache)
2. Resize to 1280×720
3. Add dark overlay (0.52 opacity) for readability
4. Render text: hook_title_text (60pt, bold, white, center)
5. Render channel name: CHANNEL_NAME (top-left corner, 32pt)
6. Save JPEG (quality=95)
```

---

### 6. **upload_agent.py** - YouTube Publishing

**Responsibility**: Upload video + thumbnail to YouTube  
**Inputs**: video.mp4, thumbnail.jpg, script metadata  
**Outputs**: YouTube URL  
**Authentication**: OAuth2 (user approves once, refresh token persists)  
**Secrets Required**:
- `YOUTUBE_TOKEN_JSON` — OAuth2 refresh token
- `YOUTUBE_CLIENT_SECRETS` — OAuth2 client credentials

**Upload Flow**:
```
1. Initialize YouTube API v3 client
2. Build video metadata (title, description, tags, category)
3. Set playlist: "AutoTube" (creates on first run)
4. Resumable upload (handles network interruptions)
5. Set thumbnail after video upload
6. Wait for processing
7. Print YouTube URL
```

**Visibility**: Videos uploaded as UNLISTED by default (safety before public launch)

---

## Integration Points

### **Config.py** - Single Source of Truth

```python
# Core Settings
CHANNEL_NICHE = "AI & Tech"  # Affects subreddits, RSS feeds, colors
CHANNEL_NAME = "AutoTube"    # Watermark + thumbnail text
SCRIPT_WORD_COUNT = 650      # ~4.5 min video (max: 800)

# Model Selection
SCRIPT_MODEL_PROVIDER = "claude"  # or "gemini"
VIDEO_ANIMATION_MODE = "kling"   # "ken_burns", "seedance", "pika"
VIDEO_BACKGROUND_MODE = "ai_images"  # or "pexels"

# Behavioral Flags
MUSIC_ENABLED = True  # Include CC0 background music
DARK_OVERLAY_OPACITY = 0.52  # Thumbnail darkness (0.4-0.65)

# Upload Scheduling
UPLOAD_TIMES_IST = [9, 12, 15, 18]  # Hours in Indian Standard Time
```

**Auto-Conversion**: IST → UTC happens automatically (subtracts 330 minutes)

---

## API Keys & Secrets

### Required (for basic operation)
| Key | Source | Cost | Purpose |
|-----|--------|------|---------|
| `ANTHROPIC_API_KEY` | Anthropic console | Paid | Claude script generation |
| `PEXELS_API_KEY` | Pexels.com | Free | B-roll stock videos |
| `YOUTUBE_TOKEN_JSON` | YouTube OAuth2 | Free | Upload videos to YouTube |
| `YOUTUBE_CLIENT_SECRETS` | Google Cloud console | Free | OAuth2 credentials |

### Optional (for premium features)
| Key | Source | Cost | Purpose |
|-----|--------|------|---------|
| `KLING_ACCESS_KEY` | app.klingai.com/dev | Free tier: 66 credits/day | AI video generation |
| `KLING_SECRET_KEY` | app.klingai.com/dev | Free tier: 66 credits/day | JWT authentication |
| `GEMINI_API_KEY` | Google AI Studio | Paid | Gemini script generation (alternative to Claude) |
| `FAL_API_KEY` | fal.ai | Paid | Pika video generation (alternative to Kling) |
| `REPLICATE_API_KEY` | Replicate.com | Paid | Video upscaling, effects |

---

## Video Generation Deep Dive

### Why Three Fallback Modes?

**Mode 1: Kling AI (PRIMARY)** ⭐
- **Quality**: Cinematic, realistic motion, 720p
- **Generation Time**: 60-90 seconds per video
- **Cost**: $0 within 66-credit free tier (~6-10 videos/day)
- **Risk**: Quota exhaustion, API downtime
- **Use Case**: Primary production pipeline

**Mode 2: Ken Burns (FALLBACK 1)**
- **Quality**: Smooth animated zoom/pan on static image
- **Generation Time**: ~2 minutes total (no API wait)
- **Cost**: FREE (Pollinations AI + FFmpeg)
- **Risk**: None (always available)
- **Use Case**: Quota exhaustion, API overload, fast prototyping
- **Animation Presets**: 17 types (zoom_in, pan_left, drift_slow, spiral, etc.)

**Mode 3: Pexels (FALLBACK 2)**
- **Quality**: Stock footage (lower visual novelty)
- **Generation Time**: Instant (cached)
- **Cost**: FREE
- **Risk**: Limited variety, may need multiple videos
- **Use Case**: Kling + Ken Burns both unavailable

**Mode 4: Gradient (FALLBACK 3)**
- **Quality**: Plain color background + text
- **Generation Time**: Instant
- **Cost**: FREE
- **Risk**: None (absolute fallback)
- **Use Case**: Last resort (rarely needed)

**Fallback Chain Logic** (video_agent.py):
```python
if primary_mode == "kling":
    modes = ["kling", "ken_burns", "pexels", "gradient"]
else:
    modes = [primary_mode, "ken_burns", "pexels", "gradient"]

for mode in modes:
    result = try_generate_with_mode(mode)
    if result:
        return result  # Success, stop fallback
    else:
        continue       # Try next mode
```

---

## Critical Implementation Details

### MoviePy 2.x vs 1.x (IMPORTANT!)

Your codebase uses **MoviePy 2.2.1** (released 2024). The API is COMPLETELY DIFFERENT from 1.x.

**Wrong (MoviePy 1.x style) — Will FAIL silently:**
```python
video = VideoFileClip("image.jpg").set_duration(5)
```

**Correct (MoviePy 2.x style):**
```python
video = VideoFileClip("image.jpg").with_duration(5)
```

**All transformations use chaining:**
```python
clip = (VideoFileClip("image.jpg")
    .with_duration(5)
    .resized(new_size=(1920, 1080))
    .with_audio(audio_track)
    .with_position("bottom")
    .with_opacity(0.8)
    .with_start(2))
```

---

### GitHub Actions Workflow

**File**: `.github/workflows/daily_pipeline.yml`

**Schedule** (4 times daily):
```yaml
schedule:
  - cron: '30 3 * * *'   # 03:30 UTC = 09:00 IST
  - cron: '30 6 * * *'   # 06:30 UTC = 12:00 IST
  - cron: '30 9 * * *'   # 09:30 UTC = 15:00 IST
  - cron: '30 12 * * *'  # 12:30 UTC = 18:00 IST
```

**Environment Variables**:
```yaml
ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
KLING_ACCESS_KEY: ${{ secrets.KLING_ACCESS_KEY }}
KLING_SECRET_KEY: ${{ secrets.KLING_SECRET_KEY }}
PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY }}
SCRIPT_MODEL_PROVIDER: ${{ vars.SCRIPT_MODEL_PROVIDER }}
VIDEO_ANIMATION_MODE: ${{ vars.VIDEO_ANIMATION_MODE }}
```

**Execution**:
```bash
python orchestrator.py --mode render --count 1
```

**Output**: Logs uploaded as artifact (14-day retention) for debugging

---

## Testing & Validation

### Local Testing (Before Commit)

**Dry Run** (no upload):
```bash
.venv/bin/python3 orchestrator.py --dry-run --topic "AI in 2025"
```

**Expected Output**:
- `outputs/<date>_<id>/` directory created
- `video.mp4` generated (1920×1080, ~4-5 min)
- `thumbnail.jpg` created (1280×720)
- Logs show all stages completed

**Full Run** (with upload):
```bash
.venv/bin/python3 orchestrator.py --mode render --count 1 --upload
```

### Pre-Commit Checklist

Before pushing code:
1. ✅ Run `--dry-run`, verify video plays
2. ✅ Check logs for API errors
3. ✅ Verify MoviePy 2.x syntax (no `.set_*()` methods)
4. ✅ Confirm no hardcoded API keys in code
5. ✅ Test new API integrations with real requests

---

## Known Limitations & Gotchas

### 1. Kling API Endpoint (CRITICAL)
- **Correct**: `https://api-singapore.klingai.com/v1/videos/text2video`
- **Wrong**: `https://api.klingai.com` (outdated)
- **Polling**: `/v1/videos/text2video/{task_id}` (NOT `/v1/videos/{task_id}`)

### 2. Movie PY Versioning
- Only version 2.x installed (`moviepy==2.2.1`)
- 1.x code will run but produce broken output
- Always test video locally before commit

### 3. Font Availability
- Auto-detects system fonts (Arial, Helvetica, etc.)
- Falls back to PIL default if missing
- Windows, Mac, Linux paths differ

### 4. Pexels Free Tier Limit
- 1 clip per search (not 30+)
- Rate limited (check headers)
- Cache videos in `outputs/video_cache/` by URL hash

### 5. Credit Tracking
- Kling free tier: 66 credits/day
- Cost: ~10 credits per 5-second video
- No client-side quota checking; API returns 402 when exhausted

### 6. YouTube Upload Resumable Limits
- Max 5GB file size
- Max 12 hours of video per account (increases as channel grows)
- Unlisted by default (visible to anyone with link)

---

## Cost Analysis (Realistic)

### Daily Production (4 videos/day = 120/month)

| Component | Cost | Notes |
|-----------|------|-------|
| **Kling AI** | $0 | 66 free credits/day, can do ~6-10 videos |
| **Pollinations.ai** | $0 | Unlimited free tier |
| **Pexels** | $0 | Free with API key |
| **Edge-TTS** | $0 | Free, unlimited |
| **Claude API** | ~$0.50-2/month | Script generation, 650 words × 4 videos × 30 days |
| **YouTube** | $0 | Free upload, no fees |
| **GitHub Actions** | $0 | Free tier includes CI/CD |
| **TOTAL** | ~$1-2/month | Essentially free |

### Scaling With Premium (If Kling quota exhausted)

| Upgrade | Cost | Benefit |
|---------|------|---------|
| Kling paid | $0.07-0.14/sec | Unlimited videos, 1080p pro mode |
| Pika API (fal.ai) | $0.08-0.15/video | Premium quality, 10x slower |
| Replicate (community) | $0.00-0.05/video | Open-source models, variable quality |

---

## Future Roadmap

### Phase 1: GCP Integration (Planned)
- Imagen 4 for images ($0.02/image, $0.12/video)
- Veo 3.1 for video ($4/video, optional premium)
- Leverage $300 free GCP credits (90 days)
- **Status**: Plan documented, awaiting implementation approval

### Phase 2: Analytics Integration
- Track view counts, engagement metrics
- Auto-optimize topics based on performance
- A/B test script styles

### Phase 3: Multi-Language Support
- Generate videos in Spanish, Hindi, French, etc.
- Localize voice, captions, music
- Expand geographic reach

---

## Deployment Checklist

### Before Going Live

- [ ] Test dry-run locally: `orchestrator.py --dry-run`
- [ ] Verify GitHub Secrets are set (no missing keys)
- [ ] Check `config.py` for channel-specific settings
- [ ] Test YouTube OAuth2 token refresh
- [ ] Run 1 full production test (--upload)
- [ ] Verify video quality on YouTube
- [ ] Check for logging/privacy issues in commits

### Week 1 Monitoring

- [ ] Monitor logs for errors (GitHub Actions Artifacts)
- [ ] Check Kling API status daily (credit usage)
- [ ] Verify videos upload and appear live
- [ ] Review YouTube Analytics for impressions/clicks

---

## Support & Debugging

### Common Issues

**"Video generation exceeded timeout"**
- Kling API slow (check klingai.com status)
- Solution: Increase `MAX_POLLING_SECONDS` in kling_video_agent.py

**"MoviePy: AttributeError set_audio()"**
- Using MoviePy 1.x syntax
- Fix: Use `.with_audio()` instead of `.set_audio()`

**"YouTube upload returns 401"**
- OAuth2 token expired
- Fix: Delete `token.pickle`, re-authenticate next run

**"Kling credits exhausted"**
- Quota hit (66 credits/day renewable)
- Fallback: Ken Burns mode activates automatically

---

## Conclusion

AutoTube is a **production-ready, cost-effective, fully automated** YouTube video generation system. It demonstrates:

✅ **Multi-agent orchestration** (6+ specialized agents)  
✅ **Resilient fallback architecture** (4-layer video generation)  
✅ **Zero-server operation** (GitHub Actions only)  
✅ **Cost optimization** ($0-2/month for 120+ videos)  
✅ **Professional output quality** (1920×1080, AI-generated, music, captions)

The system is designed to run autonomously 4 times daily and requires only API key management for ongoing operation.

---

**Report Generated**: April 19, 2026  
**Repository**: /Users/harshdeepsingh/Projects/git_projects/autotube  
**Status**: ✅ Production-Ready (Kling API Fixed)
