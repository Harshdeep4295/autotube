# Shorts from Existing Videos — Cron Job Strategy

## Problem
You have 38+ existing 16:9 videos. Instead of generating new content, create 9:16 Shorts versions of the best-performing existing videos and post them to YouTube Shorts.

## Solution: Multi-Phase Approach

### Phase 1: Extract & Re-Upload Existing Videos as Shorts

**New script:** `agents/shorts_from_existing_agent.py`

Purpose: Read existing video from `data/posted_videos.json`, download it from YouTube, re-encode to 9:16 Shorts format, and re-upload as a Shorts video.

```python
class ShortsFromExistingAgent:
    def process_video(self, video_id: str, original_title: str) -> Dict:
        """
        1. Download original video from YouTube (using YouTube API or yt-dlp)
        2. Extract best 60-90 second clip (or entire video if <90s)
        3. Re-encode to 1080×1920 (portrait) using FFmpeg
        4. Crop/zoom to keep action in center
        5. Add original title + "Shorts" overlay
        6. Extract audio from original
        7. Re-upload to YouTube as new Shorts video
        """
```

### Phase 2: Cron Jobs to Automate Shorts Generation

**Job 1: Daily Shorts Generator (picks top video from last 7 days)**
```bash
# Every day at 2 PM IST (08:30 UTC)
30 8 * * * cd /Users/harshdeepsingh/Projects/git_projects/autotube && \
  SHORTS_FROM_EXISTING=true VIDEO_FORMAT=shorts python orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views
```

**Job 2: Weekly Evergreen Shorts (picks highest-viewed video of all time)**
```bash
# Every Sunday at 9 AM IST (03:30 UTC)
30 3 * * 0 cd /Users/harshdeepsingh/Projects/git_projects/autotube && \
  SHORTS_FROM_EXISTING=true VIDEO_FORMAT=shorts python orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best
```

**Job 3: Batch Process (create 3 Shorts from top 3 underutilized videos)**
```bash
# Every 3 days at 6 PM IST (12:30 UTC)
30 12 */3 * * cd /Users/harshdeepsingh/Projects/git_projects/autotube && \
  SHORTS_FROM_EXISTING=true VIDEO_FORMAT=shorts python orchestrator.py --mode shorts_from_existing --pick_strategy underutilized --batch 3
```

## Implementation Steps

### Step 1: Add Config Fields in `config.py`

```python
SHORTS_FROM_EXISTING: bool = field(
    default_factory=lambda: os.getenv("SHORTS_FROM_EXISTING", "false").lower() == "true"
)
SHORTS_PICK_STRATEGY: str = field(
    default_factory=lambda: os.getenv("SHORTS_PICK_STRATEGY", "recent_high_views")
)
# Options: "recent_high_views", "all_time_best", "underutilized", "manual"
SHORTS_VIDEO_ID_OVERRIDE: str = field(
    default_factory=lambda: os.getenv("SHORTS_VIDEO_ID_OVERRIDE", "")
)
SHORTS_EXTRACTION_MODE: str = field(
    default_factory=lambda: os.getenv("SHORTS_EXTRACTION_MODE", "clip")
)
# Options: "clip" (60-90s best segment), "full" (entire video if <90s), "manual"
SHORTS_EXTRACT_START: int = field(
    default_factory=lambda: int(os.getenv("SHORTS_EXTRACT_START", "0"))
)
SHORTS_EXTRACT_END: int = field(
    default_factory=lambda: int(os.getenv("SHORTS_EXTRACT_END", "0"))
)
```

### Step 2: Create `agents/shorts_from_existing_agent.py`

Key methods:
- `pick_video_to_convert()` — select from `data/posted_videos.json` using strategy
- `download_from_youtube()` — use yt-dlp to grab video from YouTube
- `extract_best_clip()` — find most interesting 60-90s segment (loudest audio, most motion detection)
- `reencode_to_shorts_format()` — FFmpeg: 1080×1920, zoom-in effect (ken_burns on existing video)
- `add_overlay_text()` — Pillow: add original title + "Shorts Edition" + link to original
- `upload_as_shorts()` — use existing `UploadAgent` but with Shorts-specific metadata

### Step 3: Modify `orchestrator.py`

Add a new mode:
```python
def run_shorts_from_existing(self, pick_strategy: str = "recent_high_views", batch: int = 1):
    """Convert existing videos to Shorts format and upload."""
    from agents.shorts_from_existing_agent import ShortsFromExistingAgent
    
    agent = ShortsFromExistingAgent()
    videos = agent.pick_videos(strategy=pick_strategy, count=batch)
    
    for video in videos:
        # Re-encode and upload
        result = agent.process_video(video["video_id"], video["title"])
        if result["success"]:
            logger.info(f"Shorts created from {video['video_id']}")
        else:
            logger.warning(f"Failed to convert {video['video_id']}")
```

## Cron Syntax for Your System

Add to `crontab -e`:

```bash
# Daily Shorts from recent high-view videos (2 PM IST)
30 8 * * * cd /Users/harshdeepsingh/Projects/git_projects/autotube && SHORTS_FROM_EXISTING=true VIDEO_FORMAT=shorts python orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views >> logs/shorts_cron.log 2>&1

# Weekly best-of-all-time Shorts (Sunday 9 AM IST)
30 3 * * 0 cd /Users/harshdeepsingh/Projects/git_projects/autotube && SHORTS_FROM_EXISTING=true VIDEO_FORMAT=shorts python orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best >> logs/shorts_cron.log 2>&1

# Tri-weekly batch: 3 underutilized videos (every 3 days, 6 PM IST)
30 12 */3 * * cd /Users/harshdeepsingh/Projects/git_projects/autotube && SHORTS_FROM_EXISTING=true VIDEO_FORMAT=shorts python orchestrator.py --mode shorts_from_existing --pick_strategy underutilized --batch 3 >> logs/shorts_cron.log 2>&1
```

## Why This Approach?

| Benefit | Why It Matters |
|---------|---------------|
| **Leverage existing content** | 38 videos already made — repurpose high-performers |
| **Parallel to new uploads** | Don't interfere with daily pipeline (different script, different mode) |
| **YouTube Shorts algorithm boost** | Shorts get more impressions than long-form (3-60s vs 5 min) |
| **Lower effort** | Extract + re-encode, no new script/voice/research needed |
| **SEO benefit** | Same topic appears as both long-form and short-form (algorithm favors this) |
| **Audience reach** | TikTok/YouTube Shorts users != long-form viewers (capture both) |
| **Recurring revenue** | Shorts monetize separately once channel hits 1K subs |

## Pick Strategies Explained

### 1. **recent_high_views** (Default)
- Looks at videos from last 7 days
- Picks the one with most views
- Run daily (always fresh content)

### 2. **all_time_best**
- All 38 videos, sorted by view count
- Picks #1 ranked video (never repeated)
- Rotates through top 10 weekly

### 3. **underutilized**
- Videos with <500 views or very old
- Revive old content
- Re-expose to audience

### 4. **manual**
```bash
SHORTS_FROM_EXISTING=true SHORTS_VIDEO_ID_OVERRIDE=dQw4w9WgXcQ python orchestrator.py --mode shorts_from_existing
```

## Testing Before Cron

```bash
# Test with a specific video (don't upload, just prepare files)
SHORTS_FROM_EXISTING=true VIDEO_FORMAT=shorts SHORTS_VIDEO_ID_OVERRIDE=dQw4w9WgXcQ \
  python orchestrator.py --dry-run --mode shorts_from_existing

# Check outputs/
# Should have:
# - shorts_converted_*.mp4 (1080×1920)
# - shorts_thumbnail_*.jpg (1080×1920)
# - shorts_script_*.json (with original title + "#Shorts")
```

## Playlist Integration

With `PLAYLIST_ENABLED=true` (now default):
- Shorts created from existing videos automatically added to a "Shorts" playlist
- Keyword matching: "Shorts" → finds/creates "Shorts" playlist
- Viewers can binge all Shorts in one playlist

## Cost Analysis

| Component | Cost | Per Video |
|-----------|------|-----------|
| YouTube download | Free | $0 |
| FFmpeg re-encode (local) | Free | $0 |
| YouTube upload | Free | $0 |
| **Total** | **Free** | **$0** |

No API costs, no server costs — completely local processing.

## Timeline

- **Week 1:** Implement `ShortsFromExistingAgent` + orchestrator mode
- **Week 2:** Test with 3 videos, refine re-encoding quality
- **Week 3:** Deploy cron jobs, monitor first batch
- **Ongoing:** Adjust strategies based on click-through rates

## Why PLAYLIST_ENABLED=true by Default?

With Shorts generation running 3x/week, you'll accumulate:
- 3 Shorts/week × 52 weeks = 156 Shorts/year
- Without auto-playlists: 156 videos scattered across channel
- With auto-playlists: Organized into "Shorts", "Recent", "Best Of" playlists
- **Result:** Better viewer retention, higher watch-through rate, algorithm boost

That's why it's on by default.
