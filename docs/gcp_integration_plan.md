# GCP Integration Plan for AutoTube

## Overview

This document captures the complete research and verified technical plan for integrating Google Cloud Platform services (Imagen 4, Veo 3.1) into AutoTube. **No code has been implemented yet.** This is a reference for future work.

Research completed: April 18, 2026. Based on SDK version `google-genai==1.73.1`.

---

## Why GCP?

You have **$300 free trial credits** (90 days). This research evaluates the ROI for using GCP services to improve AutoTube's video quality.

| Service | Best Use | Cost/Video | From $300 |
|---|---|---|---|
| **Imagen 4** (images) | Replace Pollinations | $0.12 | **2,500 videos** ✅ |
| **Veo 3.1** (video) | Cinematic clips | $24 | 12 videos ❌ |
| **Ken Burns** (current) | Production default | $0 | ∞ ✅ |

**Honest assessment:** Veo is too expensive for daily production (4×/day). The real value is **Imagen 4 for images** — replaces Pollinations with production-grade quality. Veo is useful only for occasional "premium" videos.

---

## Phase 1: Imagen 4 (Recommended First Step)

### Problem
Pollinations.ai is free but:
- Rate-limited (unpredictable delays)
- No SLA
- Inconsistent output quality
- No official support

### Solution
Imagen 4 on Vertex AI:
- Production SLA
- Consistent quality
- $0.02/image (6 images/video = $0.12/video)
- **$300 = 2,500 videos = ~1.7 years of daily uploads**

### Setup Required (One-Time)
```
GCP Console
  → Enable Vertex AI API
  → IAM & Admin → Service Accounts → Create
  → Grant role: roles/aiplatform.user
  → Generate JSON key
  
GitHub
  → Settings → Secrets and Variables → Secrets
  → Add GCP_SERVICE_ACCOUNT_JSON (full JSON content)
```

No GCS bucket needed.

### Implementation

**Python code pattern:**
```python
from google import genai
from google.oauth2 import service_account
from google.genai.types import GenerateImagesConfig
import json

sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
sa_info = json.loads(sa_json)
creds = service_account.Credentials.from_service_account_info(
    sa_info,
    scopes=["https://www.googleapis.com/auth/cloud-platform"],  # REQUIRED
)

client = genai.Client(
    vertexai=True,
    project=sa_info["project_id"],
    location="us-central1",
    credentials=creds,
)

response = client.models.generate_images(
    model="imagen-4.0-generate-001",  # Use Imagen 4, not Imagen 3 (deprecated June 2026)
    prompt="cinematic high quality ... no text",
    config=GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio="16:9",
        output_mime_type="image/jpeg",
        person_generation="dont_allow",  # REQUIRED — people are allowlist-only
    ),
)

image_bytes = response.generated_images[0].image.image_bytes
Path("output.jpg").write_bytes(image_bytes)
```

**Where to add in codebase:** `agents/video_agent.py` → new method `_fetch_imagen4_image()` → wire into `_fetch_ai_image()` with try/except fallback to Pollinations.

---

## Phase 2: Veo 3.1 (Optional Premium Mode)

### Problem
Ken Burns is free but static (no real motion). Veo generates cinematic video.

### Solution
Veo 3.1 on Vertex AI (manual trigger only for special topics):
- Use only for 1-2 sections per video, not all 6
- Cost: $4/clip × 2 = $8/video (reasonable), or $4/clip × 6 = $24/video (expensive)
- Async generation (2-4 min per clip, must poll every 20 seconds)

### Extra Setup Required
1. Create a GCS bucket for output storage
2. Set `GCP_GCS_BUCKET` env var

**Why GCS?** Vertex AI Veo writes output to GCS only — cannot write to local disk directly. Must download via `google-cloud-storage` package.

### Implementation

**Python code pattern:**
```python
from google import genai
from google.genai import types
from google.cloud import storage as gcs
import time

operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",  # Use 3.1, not 2.0 (use latest)
    source=types.GenerateVideosSource(prompt="cinematic 4K ..."),
    config=types.GenerateVideosConfig(
        output_gcs_uri=f"gs://{bucket}/veo3_cache/",  # REQUIRED for Vertex AI
        duration_seconds=8,
        aspect_ratio="16:9",
        resolution="1080p",
        person_generation="dont_allow",
    ),
)

# Poll every 20 seconds — generation takes 2-4 minutes
while not operation.done:
    time.sleep(20)
    operation = client.operations.get(operation=operation)

# Download from GCS
gcs_uri = operation.result.generated_videos[0].video.uri
bucket_name, blob_path = gcs_uri[5:].split("/", 1)
gcs_client.bucket(bucket_name).blob(blob_path).download_to_filename("output.mp4")
```

**Where to add:** `agents/video_agent.py` → new method `_fetch_veo3_video()` → wire into `_try_section_video_chain()` fallback.

---

## Cost Analysis: $300 Breakdown

### Best Case: Imagen 4 Only
- Cost per video: $0.12 (6 images × $0.02)
- Videos from $300: **2,500**
- Timeline: ~1.7 years at 4 videos/day

### Reasonable Case: Imagen 4 + Selective Veo
- Normal video: Imagen 4 images + Ken Burns = $0.12
- Premium video (1/week): 2 Veo clips + 4 Imagen images = ~$8.08
- $300 covers: 294 normal + 8 premium = **302 videos total**

### Worst Case: Veo for All Videos
- Cost per video: $24 (6 clips × $4)
- Videos from $300: 12 videos
- ❌ Exhausts credits in 3 days at 4 videos/day

---

## Post-$300 Strategy

When $300 credits run out (or if you need to extend):

### Multiple GCP Accounts?
**Answer: No. Against ToS.**
- Google ties accounts to phone number + payment method
- Creating multiple accounts solely for credits violates terms
- Risk: all accounts suspended
- Do not recommend

### Alternatives (Free/Cheap):

| Option | Cost | Notes |
|---|---|---|
| **Ken Burns (default)** | $0 forever | Already works great |
| **MiniMax/Hailuo free credits** | $0 × 1-2 months | ~100 free credits on signup |
| **fal.ai free signup credit** | $0 × few weeks | ~$10 on signup |
| **Wan 2.1 on Replicate** | $0.08-0.15/clip | Open-source model, cheapest paid option |
| **MiniMax/Hailuo API** | $0.10/clip | After free credits exhaust |
| **Kling via fal.ai** | $0.15-0.25/clip | Best quality but expensive |
| **Self-hosted Wan 2.1** | $0 + GPU cost | RTX 3090+ only, ~2-5 min per clip |

### Recommended Long-Term Stack
```
Phase 1 (now, use $300):     Imagen 4 images + Ken Burns
Phase 2 (credits run out):   Rotate free credits (MiniMax + fal.ai) = ~1-2 months free
Phase 3 (all free exhausted): Wan 2.1 via Replicate (~$0.10/clip) or back to Ken Burns
Phase 4 (monetized):         Self-hosted Wan 2.1 on personal GPU (zero marginal cost)
```

---

## Technical Gotchas (Verified)

### Critical Must-Knows

1. **OAuth2 scopes are REQUIRED**
   - When using service account credentials with `google-genai` SDK, must pass:
   ```python
   scopes=["https://www.googleapis.com/auth/cloud-platform"]
   ```
   - Omitting scopes causes silent auth failures

2. **Person generation is allowlist-only**
   - Must always set `person_generation="dont_allow"` in config
   - If omitted and prompt contains people, API rejects it
   - Allowlist request form is broken (as of June 2025)

3. **Veo is async, not blocking**
   - Unlike `replicate.run()` which blocks, Veo returns immediately with an operation
   - Must poll `client.operations.get()` every 20 seconds
   - Generation takes 2-4 minutes per clip
   - Does NOT fit into synchronous pipeline without refactoring

4. **GCS bucket required for Veo**
   - Vertex AI Veo cannot write local output
   - Must specify `output_gcs_uri` in config
   - Must download from GCS afterward (need `google-cloud-storage` package)

5. **Gemini API key ≠ Vertex AI**
   - Using `api_key=GEMINI_API_KEY` does NOT draw from $300 GCP credits
   - Must use service account with `vertexai=True` to use credits
   - Separate billing paths entirely

6. **Use Imagen 4, not Imagen 3**
   - Imagen 3 model: `imagen-3.0-generate-002` (deprecates June 30, 2026)
   - Imagen 4 model: `imagen-4.0-generate-001` (current)
   - Don't lock yourself into deprecated API

7. **Use Veo 3.1, not Veo 2**
   - Veo 2 model: `veo-2.0-generate-001` (older, 720p max)
   - Veo 3.1 model: `veo-3.1-generate-preview` (latest, 1080p, better quality)
   - Veo 3 is not a separate string — the endpoint is `veo-3.1-generate-preview`

8. **Safety filters block ~20% of prompts**
   - By design, not a bug
   - Responses can have `len(response.generated_images) == 0`
   - Must handle gracefully with fallback

---

## Files That Would Change (Implementation Checklist)

If/when implemented, these files need updates:

| File | Change | Complexity |
|---|---|---|
| `agents/video_agent.py` | Add `_fetch_imagen4_image()` | Medium (100 lines) |
| `agents/video_agent.py` | Add `_fetch_veo3_video()` | Medium-Hard (150 lines, async polling) |
| `agents/video_agent.py` | Wire into `_fetch_ai_image()` | Low (5 lines) |
| `agents/video_agent.py` | Wire into `_try_section_video_chain()` | Low (10 lines) |
| `requirements.txt` | Add `google-cloud-storage>=2.0.0` | Trivial (1 line) |
| `.github/workflows/daily_pipeline.yml` | Pass GCP env vars | Low (2 lines) |
| `.github/workflows/prefetch_pipeline.yml` | Pass GCP env vars | Low (2 lines) |
| `CLAUDE.md` | Document GCP gotchas & secrets | Low (20 lines) |

No changes to `config.py` — credentials come via env vars directly (same pattern as `REPLICATE_API_KEY`).

---

## Verification Commands (Before/After Implementation)

```bash
# Test Imagen 4 alone (no GCS needed)
export GCP_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
VIDEO_IMAGE_PROVIDER=imagen4 .venv/bin/python3 orchestrator.py --dry-run --topic "AI in 2025"
# Expected output: "Imagen 4 image downloaded: imagen4_*.jpg" ✅

# Test Veo 3.1 (requires GCS bucket)
export GCP_GCS_BUCKET=your-bucket-name
VIDEO_ANIMATION_MODE=veo3 .venv/bin/python3 orchestrator.py --dry-run --topic "AI in 2025"
# Expected output: "Veo 3 video downloaded: veo3_*.mp4" (after 2-4 min wait) ✅

# Test fallback (remove creds — should fall back to Pollinations)
unset GCP_SERVICE_ACCOUNT_JSON
.venv/bin/python3 orchestrator.py --dry-run --topic "AI in 2025"
# Expected output: "Imagen 4 failed, falling back to Pollinations" + video succeeds ✅
```

---

## Decision Guide: Should You Implement This?

✅ **Implement Phase 1 (Imagen 4) if:**
- You want higher-quality, consistent images
- You want production SLA and no rate limits
- You're OK with $0.12/video cost (sustainable for 1.7 years from $300)

❓ **Implement Phase 2 (Veo 3.1) if:**
- You have "best of" topics that deserve premium cinematic treatment
- You're OK with 2-4 min generation time per clip (doesn't block daily pipeline)
- You plan to use selectively (1-2 sections per video max)

❌ **Don't implement if:**
- Ken Burns quality is acceptable for your channel (it is for most faceless YT)
- You want zero setup complexity
- You can't justify $8-24 per premium video

---

## Resources

- **Official Docs:**
  - [Vertex AI Imagen 4 API](https://cloud.google.com/vertex-ai/generative-ai/docs/models/imagen-overview)
  - [Vertex AI Veo API](https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo)
  - [google-genai Python SDK](https://googleapis.github.io/python-genai/)

- **Gotcha Sources:**
  - SDK source: `google-genai==1.73.1`
  - Person generation allowlist: [Google Developer Forums](https://discuss.google.dev/t/imagen-3-generating-images-containing-people-is-currently-an-allowlist-only-feature)
  - Service account scopes: [pgaleone.eu article](https://pgaleone.eu/cloud/2025/06/29/vertex-ai-to-genai-sdk-service-account-auth-python-go/)

---

## Notes for Future Implementation

1. Start with Phase 1 (Imagen 4) — lowest risk, highest ROI
2. Test Phase 1 thoroughly before touching Phase 2
3. Phase 2 (Veo) requires async polling — may need orchestrator refactor
4. Plan for graceful fallback to Pollinations + Ken Burns if GCP creds not available
5. Monitor $300 credit usage in GCP Console → set billing alert at $250
6. Before credits run out, switch default back to Ken Burns permanently
