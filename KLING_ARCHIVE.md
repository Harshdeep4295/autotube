# Kling AI Integration Archive

**Status:** DISABLED (2026-04-28)  
**Reason:** Cost concerns and reliability issues. Removed from active pipeline but preserved for future reference.

---

## Overview

Kling AI (via Kuaishou) provides text-to-video generation using `kling-v2.6-pro` model.

- **API:** `https://api-singapore.klingai.com`
- **Authentication:** JWT-based (HS256)
- **Cost:** Credit-based billing
- **Generation Time:** ~60 seconds per 5-second video
- **Quality:** High-quality cinematic videos

---

## Setup Requirements

### 1. Get Kling Credentials

1. Register at Kling AI (https://klingai.com)
2. Create API credentials (Access Key + Secret Key)
3. Add daily credits to account (costs vary, ~$0.05-0.10 per video)

### 2. Environment Variables

```bash
KLING_ACCESS_KEY=your_access_key
KLING_SECRET_KEY=your_secret_key
KLING_WEBHOOK_SECRET=your_webhook_secret  # optional, for async notifications
```

### 3. GitHub Secrets (if using CI/CD)

Add the above as GitHub repository secrets in Settings → Secrets and Variables.

---

## Code Location

**Removed Files:**
- `agents/kling_video_agent.py` — Main Kling integration (450 lines)
- `agents/kling_quota_manager.py` — Daily quota tracking

**Removed References:**
- `agents/video_agent.py` — Lines: 36, 134, 319-320, 329, 335-354, 1027-1049
- `.github/workflows/daily_pipeline.yml` — Kling env vars
- `.github/workflows/prefetch_pipeline.yml` — Kling env vars

---

## How It Worked

### Text-to-Video Flow

```
1. Submit prompt → POST /v1/videos/text2video
   ↓
2. Get task_id (immediate response)
   ↓
3. Poll task status every 5 seconds → GET /v1/videos/text2video/{task_id}
   ↓
4. Status becomes "succeed" → extract video URL
   ↓
5. Download from temp CDN → cache locally
```

### Key Classes

**KlingJWTAuth**
- Generates JWT tokens (30-min expiry)
- Caches tokens to reduce auth overhead
- Automatic renewal on expiry

**KlingAPIClient** (async)
- HTTP client with error handling
- Endpoint: `_request(method, endpoint, **kwargs)`
- Handles: 401 (auth), 402 (quota), 404 (task not found), 429 (rate limit), 5xx (server)

**KlingVideoGenerator**
- High-level orchestrator
- Methods:
  - `submit()` — Fire-and-forget task submission
  - `check_and_download()` — Poll and download if ready
  - `generate()` — Full synchronous generation

---

## Known Issues

❌ **Daily Quota Limits**
- Fixed 402 error when daily credits exhausted
- API response unclear about remaining credits

❌ **Slow Polling**
- Generation takes ~60s, but API sometimes returns 404 during processing
- Fixed with 5s poll interval + 5min timeout

❌ **Content Policy**
- Prompts blocked unexpectedly (e.g., "data visualization" flagged as too vague)
- Error responses inconsistent

❌ **Temporary URLs**
- Video URLs expire after 24 hours
- Must cache immediately after download

---

## API Error Codes

| Code | Cause | Fix |
|------|-------|-----|
| 401 | Invalid/expired credentials | Check KLING_ACCESS_KEY, KLING_SECRET_KEY |
| 402 | Daily quota exhausted | Add credits, retry next day |
| 404 | Task not found | Task still processing (normal), or task ID invalid |
| 429 | Rate limited | Exponential backoff |
| 5xx | Server error | Retry with backoff |

---

## To Re-Enable Kling

### Step 1: Restore Files

```bash
# Restore from git history
git checkout 5ae7350 -- agents/kling_video_agent.py agents/kling_quota_manager.py
```

### Step 2: Update video_agent.py

Restore these sections (search for "RESTORE KLING"):

```python
# Line 36
from agents.kling_video_agent import KlingVideoGenerator

# Line 134
self.kling_generator = None

# Lines 319-354
elif primary_mode == "kling":
    modes = ["kling", "ken_burns", "pexels"]
    # ... (full code in git history)

# Lines 1027-1049
if config.VIDEO_ANIMATION_MODE == "kling":
    # ... (full code in git history)
```

### Step 3: Add Secrets to GitHub

Settings → Secrets and Variables → New repository secret:
- `KLING_ACCESS_KEY`
- `KLING_SECRET_KEY`
- `KLING_WEBHOOK_SECRET` (optional)

### Step 4: Update Workflows

In `.github/workflows/daily_pipeline.yml` and `prefetch_pipeline.yml`, add:

```yaml
env:
  KLING_ACCESS_KEY: ${{ secrets.KLING_ACCESS_KEY }}
  KLING_SECRET_KEY: ${{ secrets.KLING_SECRET_KEY }}
  KLING_WEBHOOK_SECRET: ${{ secrets.KLING_WEBHOOK_SECRET }}
```

### Step 5: Set Video Mode

```bash
# Via env var
VIDEO_ANIMATION_MODE=kling python orchestrator.py --mode render

# Or set GitHub Variable (Settings → Variables)
VIDEO_ANIMATION_MODE=kling
```

---

## Fallback Chain (When Kling Enabled)

If primary mode is `kling`:

1. Try Kling
2. Fallback to Ken Burns
3. Fallback to Pexels clips
4. Fallback to gradient background

---

## Cost Calculator

**Kling Pricing** (varies by region):
- ~$0.05-0.10 per 5-second video
- Daily limit: varies (typically 50-200 daily credits)

**Calculation:**
- 4 videos/day × $0.08 per video = **$0.32/day**
- Monthly: $0.32 × 30 = **~$10/month** (with free tier)
- Production: Much higher if scaling

**Why disabled:** Cost + reliability → switched to free alternatives (Ken Burns, ZSky AI, HunyuanVideo)

---

## Useful Links

- **Kling Official:** https://klingai.com
- **API Docs:** https://klingai.com/docs
- **Support:** support@klingai.com
- **Pricing:** https://klingai.com/pricing

---

## Notes for Future

- Kling v3.0+ may have better reliability
- Check if they offer free tier / better pricing before re-enabling
- Consider as fallback-only mode (don't make it primary)
- Test thoroughly before committing credits

