# Path B: GCP Vertex AI Veo 3.1 — Complete Implementation Guide

**Status:** Production-ready specification  
**Research Depth:** Comprehensive (14 implementation areas covered)  
**Complexity:** High (GCP setup, async polling, GCS bucket, service accounts)  
**Timeline:** 3-4 days implementation + 2 days testing

---

## Executive Summary

GCP Vertex AI **Veo 3.1** provides cinematic text-to-video generation powered by **$300 free trial credits** (90-day expiration). Output includes **native audio synthesis** (unique differentiator), making videos more engaging than Ken Burns alone.

**Key metrics:**
- Free tier: $300 credits (90 days)
- Cost: $0.10-0.75/second depending on model variant
- 5-second video cost: $0.40-$6.00 depending on resolution/variant
- Generation time: 2-4 minutes per video
- Quality: 720p-4K cinematic with audio
- Use case: Premium content, A/B testing quality impact

---

## Part 1: GCP Account Setup

### Step 1: Create GCP Project

1. Go to **https://console.cloud.google.com**
2. Create new project:
   - Name: `autotube-veo`
   - Organization: (your organization)
3. Enable billing (required for Vertex AI, even with free trial)
4. Copy **Project ID** (format: `autotube-veo-abc123`)

### Step 2: Enable Vertex AI API

```bash
# Using gcloud CLI
gcloud services enable aiplatform.googleapis.com --project=autotube-veo-abc123

# Or manually:
# GCP Console → APIs & Services → Enable APIs and Services
# Search "Vertex AI API" → Enable
```

### Step 3: Create Service Account

**Via GCP Console:**
1. Go to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
   - Service account name: `autotube-veo`
   - Service account ID: `autotube-veo@autotube-veo-abc123.iam.gserviceaccount.com`
3. Click **Create and Continue**
4. Grant role: **`roles/aiplatform.user`** (NOT Editor or Owner)
5. Click **Continue** → **Done**

### Step 4: Generate JSON Key

1. Click on service account you just created
2. Go to **Keys** tab
3. Click **Add Key → Create new key**
4. Choose **JSON** format
5. **Download immediately** (shown only once)
6. Store securely

**JSON key format:**
```json
{
  "type": "service_account",
  "project_id": "autotube-veo-abc123",
  "private_key_id": "key_id_here",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "autotube-veo@autotube-veo-abc123.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

### Step 5: Create GCS Bucket

Veo writes output to Google Cloud Storage (GCS), not local disk.

**Via gcloud CLI:**
```bash
gsutil mb -p autotube-veo-abc123 -l us-central1 gs://autotube-veo-output
gsutil acl ch -u autotube-veo@autotube-veo-abc123.iam.gserviceaccount.com:OWNER gs://autotube-veo-output
```

**Or via Console:**
1. Go to **Cloud Storage → Buckets**
2. Click **Create**
   - Bucket name: `autotube-veo-output`
   - Region: `us-central1`
   - Storage class: `Standard`
3. Click **Create**

### Step 6: Grant Bucket Permissions

```bash
# Grant service account write access to bucket
gsutil iam ch serviceAccount:autotube-veo@autotube-veo-abc123.iam.gserviceaccount.com:roles/storage.objectAdmin gs://autotube-veo-output
```

Or via Console:
1. Go to **Cloud Storage → Buckets → Your Bucket**
2. Go to **Permissions** tab
3. Click **Grant Access**
4. Add principal: `autotube-veo@autotube-veo-abc123.iam.gserviceaccount.com`
5. Role: `Storage Object Admin`
6. Click **Save**

### Step 7: Store Credentials

**Create `.env` file (never commit):**
```bash
# .env
GCP_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"autotube-veo-abc123",...}'
GCP_GCS_BUCKET=autotube-veo-output
GCP_PROJECT_ID=autotube-veo-abc123
```

**For GitHub Secrets:**
```
Settings → Secrets and Variables → Secrets
- GCP_SERVICE_ACCOUNT_JSON: (full JSON as string, can be multi-line)
- GCP_GCS_BUCKET: autotube-veo-output
- GCP_PROJECT_ID: autotube-veo-abc123
```

**Important:** Store the full JSON as a single line string in GitHub Secrets.

---

## Part 2: Install Dependencies

```bash
pip install google-genai==1.73.1 google-cloud-storage>=2.0.0 google-auth
```

**Verify installation:**
```bash
python -c "from google import genai; print(genai.__version__)"
# Should show: 1.73.1
```

---

## Part 3: Core Implementation

### File: `agents/gcp_veo_agent.py` (NEW)

```python
"""
GCP Vertex AI Veo 3.1 Video Generation
- Text-to-video generation with async polling
- Service account authentication
- GCS bucket for video output storage
- 2-4 minute generation time
"""

import asyncio
import logging
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from google import genai
from google.oauth2 import service_account
from google.cloud import storage as gcs
from google.api_core import exceptions as gcp_exceptions

from config import config

logger = logging.getLogger(__name__)

# Configuration
VEO_MODEL = "veo-3.1-generate-001"  # Use GA, not preview
VEO_REGION = "us-central1"
VEO_DURATION = 8  # seconds (max for standard)
VEO_RESOLUTION = "1080p"
VEO_ASPECT_RATIO = "16:9"
POLL_INTERVAL_SECONDS = 20  # Veo is slower than Kling
MAX_POLLING_SECONDS = 600  # 10 minutes (Veo takes 2-4 min)
DOWNLOAD_TIMEOUT_SECONDS = 3600  # 1 hour (24-hour expiration window)


@dataclass
class VeoVideoResult:
    """Result from successful Veo generation"""
    task_id: str
    video_url: str  # Permanent storage URL
    file_size_bytes: int
    duration_seconds: int
    resolution: str
    generation_time_seconds: float
    generated_at: datetime


class VeoAuthenticator:
    """GCP service account authentication"""

    def __init__(self, service_account_json: str, project_id: str):
        """
        Args:
            service_account_json: Full JSON content as string
            project_id: GCP project ID
        """
        sa_dict = json.loads(service_account_json)
        
        # CRITICAL: Scopes are REQUIRED
        self.credentials = service_account.Credentials.from_service_account_info(
            sa_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.project_id = project_id

    def get_credentials(self):
        """Get credentials for genai client"""
        return self.credentials

    def get_gcs_client(self):
        """Get GCS client for downloads"""
        return gcs.Client(
            project=self.project_id,
            credentials=self.credentials
        )


class VeoAPIClient:
    """Async Veo 3.1 API client"""

    def __init__(
        self,
        service_account_json: str,
        project_id: str,
        gcs_bucket: str,
        gcs_region: str = "us-central1"
    ):
        self.service_account_json = service_account_json
        self.project_id = project_id
        self.gcs_bucket = gcs_bucket
        self.gcs_region = gcs_region

        auth = VeoAuthenticator(service_account_json, project_id)
        self.credentials = auth.get_credentials()
        self.gcs_client = auth.get_gcs_client()

        # Initialize genai client
        self.client = genai.Client(
            vertexai=True,  # CRITICAL: Use Vertex AI, not Gemini API
            project=project_id,
            location=gcs_region,
            credentials=self.credentials
        )

        self.logger = logger

    async def submit_text_to_video(
        self,
        prompt: str,
        duration_seconds: int = VEO_DURATION
    ) -> str:
        """
        Submit text-to-video request
        Returns: operation.name (for polling)
        """
        from google.genai import types

        # Prepare GCS URI for output
        gcs_output_uri = f"gs://{self.gcs_bucket}/veo_output/"

        self.logger.info(f"Submitting Veo generation: {prompt[:100]}...")

        try:
            operation = self.client.models.generate_videos(
                model=VEO_MODEL,
                source=types.GenerateVideosSource(
                    prompt=prompt[:2000]  # Reasonable max length
                ),
                config=types.GenerateVideosConfig(
                    output_gcs_uri=gcs_output_uri,
                    duration_seconds=min(duration_seconds, 8),  # Max 8 seconds
                    aspect_ratio=VEO_ASPECT_RATIO,
                    resolution=VEO_RESOLUTION,
                    person_generation="dont_allow",  # REQUIRED
                ),
            )

            self.logger.info(f"Generation submitted: {operation.name}")
            return operation.name

        except gcp_exceptions.PermissionDenied:
            raise PermissionError(
                "Missing IAM role: roles/aiplatform.user"
            )
        except gcp_exceptions.NotFound:
            raise ValueError(
                "Invalid project ID or bucket name"
            )
        except Exception as e:
            raise APIError(f"Failed to submit generation: {e}")

    async def poll_operation(
        self,
        operation_name: str,
        timeout_seconds: int = MAX_POLLING_SECONDS
    ) -> Dict:
        """
        Poll operation until complete
        Returns: result dict with generated_videos, metadata
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Video generation exceeded {timeout_seconds}s timeout"
                )

            # Get operation status
            operation = self.client.operations.get(operation=operation_name)

            self.logger.debug(
                f"Polling {operation.name}: done={operation.done} "
                f"({elapsed:.0f}s elapsed)"
            )

            if operation.done:
                if operation.error:
                    error_msg = operation.error.message
                    self.logger.error(f"Generation failed: {error_msg}")

                    # Check for specific error types
                    if "safety" in error_msg.lower() or "policy" in error_msg.lower():
                        raise ContentPolicyViolation(error_msg)
                    else:
                        raise GenerationError(error_msg)

                # Success
                self.logger.info(f"Generation complete: {operation.name}")
                return {
                    "operation_name": operation.name,
                    "result": operation.result,
                    "duration": elapsed
                }

            # Still processing
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def download_from_gcs(
        self,
        gcs_uri: str,
        local_path: Path
    ) -> Tuple[Path, int]:
        """
        Download video from GCS to local storage
        
        Args:
            gcs_uri: gs://bucket/path/to/video.mp4
            local_path: local file path to save
        
        Returns:
            (file_path, file_size_bytes)
        """
        # Parse GCS URI
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        parts = gcs_uri[5:].split("/", 1)
        bucket_name = parts[0]
        blob_path = parts[1]

        self.logger.info(f"Downloading from GCS: {gcs_uri}")

        try:
            bucket = self.gcs_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            # Download with retries built-in
            blob.download_to_filename(str(local_path))

            file_size = local_path.stat().st_size
            self.logger.info(
                f"Downloaded: {local_path.name} ({file_size / 1024 / 1024:.1f}MB)"
            )

            return local_path, file_size

        except Exception as e:
            raise DownloadError(f"Failed to download from GCS: {e}")


class VeoVideoGenerator:
    """High-level video generation orchestrator"""

    def __init__(self):
        service_account_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
        project_id = os.getenv("GCP_PROJECT_ID")
        gcs_bucket = os.getenv("GCP_GCS_BUCKET")

        if not all([service_account_json, project_id, gcs_bucket]):
            raise ValueError(
                "GCP_SERVICE_ACCOUNT_JSON, GCP_PROJECT_ID, GCP_GCS_BUCKET required"
            )

        self.client = VeoAPIClient(
            service_account_json=service_account_json,
            project_id=project_id,
            gcs_bucket=gcs_bucket
        )

        self.storage_dir = Path(config.VIDEO_CACHE_DIR) / "gcp_veo"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        prompt: str,
        section_idx: int,
        duration: int = 8
    ) -> Optional[str]:
        """
        Generate video from prompt
        
        Returns: path to cached video file, or None if failed
        """
        # Create cache key
        cache_key = hashlib.md5(
            f"veo_{prompt}_{section_idx}_{duration}".encode()
        ).hexdigest()[:12]
        cache_path = self.storage_dir / f"veo_{cache_key}.mp4"

        # Check cache
        if cache_path.exists() and cache_path.stat().st_size > 1_000_000:
            self.logger.info(f"Using cached Veo video: {cache_path.name}")
            return str(cache_path)

        try:
            start_time = time.time()

            # Submit generation
            operation_name = await self.client.submit_text_to_video(
                prompt=prompt,
                duration_seconds=duration
            )

            # Poll until complete
            result = await self.client.poll_operation(operation_name)

            # Extract video URI
            generated_videos = result["result"].generated_videos
            if not generated_videos:
                raise GenerationError("No videos in response")

            gcs_uri = generated_videos[0].video.uri

            # Download to local storage
            await self.client.download_from_gcs(gcs_uri, cache_path)

            generation_time = time.time() - start_time
            size_mb = cache_path.stat().st_size / (1024 * 1024)

            # Estimate cost
            cost_per_sec = 0.10  # Veo Fast variant
            estimated_cost = duration * cost_per_sec

            self.logger.info(
                f"Veo video generated: {cache_path.name} "
                f"({size_mb:.1f}MB, {generation_time:.0f}s, "
                f"~${estimated_cost:.2f})"
            )

            return str(cache_path)

        except ContentPolicyViolation as e:
            self.logger.warning(f"Prompt blocked by safety filter: {e}")
            return None

        except TimeoutError:
            self.logger.warning(f"Veo generation timeout (>10 minutes)")
            return None

        except Exception as e:
            self.logger.warning(f"Veo generation failed: {e}")
            return None


# Custom Exceptions
class VeoError(Exception):
    """Base Veo exception"""
    pass


class APIError(VeoError):
    """API request error"""
    pass


class AuthenticationError(VeoError):
    """Auth failed"""
    pass


class GenerationError(VeoError):
    """Video generation failed"""
    pass


class ContentPolicyViolation(VeoError):
    """Prompt violates content policy"""
    pass


class DownloadError(VeoError):
    """Download from GCS failed"""
    pass


class TimeoutError(VeoError):
    """Operation timeout"""
    pass
```

### Step 2: Wire into VideoAgent

**File:** `agents/video_agent.py` (modify)

Add to imports:
```python
from agents.gcp_veo_agent import VeoVideoGenerator
```

Add to `__init__`:
```python
self.veo_generator = None
```

Add to fallback chain (around line 220):

```python
def _try_section_video_chain(self, section_idx: int, query: str, primary_mode: str):
    """Chain: primary_mode → Seedance → Veo → Kling → Ken Burns → Pexels → Gradient"""
    modes = []
    
    if primary_mode in ["seedance", "veo"]:
        modes.append(primary_mode)
    
    if "seedance" not in modes:
        modes.append("seedance")
    
    # NEW: Add Veo as early fallback (before Kling)
    if os.getenv("GCP_SERVICE_ACCOUNT_JSON"):  # Only if configured
        modes.append("veo")
    
    modes.append("kling")
    # ... rest of chain
    
    for mode in modes:
        try:
            if mode == "veo":
                if not self.veo_generator:
                    self.veo_generator = VeoVideoGenerator()
                
                import asyncio
                path = asyncio.run(
                    self.veo_generator.generate(query, section_idx)
                )
            # ... rest of modes
```

---

## Part 4: GitHub Actions Integration

**File:** `.github/workflows/daily_pipeline.yml` (modify)

Add environment variables:
```yaml
env:
  GCP_SERVICE_ACCOUNT_JSON: ${{ secrets.GCP_SERVICE_ACCOUNT_JSON }}
  GCP_GCS_BUCKET: ${{ secrets.GCP_GCS_BUCKET }}
  GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
```

**Important:** Don't run Veo for every video during daily pipeline (too expensive). Instead, use via conditional:

```yaml
- name: Check if should use Veo
  run: |
    # Only use Veo for premium runs (every 4th video, or manual trigger)
    if [[ "${{ github.event.inputs.use_veo }}" == "true" ]] || \
       [[ $GITHUB_RUN_NUMBER -mod 4 -eq 0 ]]; then
      echo "VEO_ENABLED=true" >> $GITHUB_ENV
    fi
```

---

## Part 5: Cost Monitoring

### Create: `agents/gcp_cost_tracker.py` (NEW)

```python
"""
GCP credit usage monitoring and alerting
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Pricing (as of April 2026)
VEO_STANDARD_COST_PER_SEC = 0.75  # $6/8-sec video
VEO_FAST_COST_PER_SEC = 0.10      # $0.80/8-sec video
VEO_LITE_COST_PER_SEC = 0.05      # $0.40/8-sec video

IMAGEN_COST_PER_IMAGE = 0.02


class GCPCostTracker:
    """Track credit usage against $300 budget"""

    def __init__(self, initial_credits: float = 300.0):
        self.initial_credits = initial_credits
        self.spent = 0.0
        self.operations = []

    def log_veo_generation(
        self,
        duration_seconds: int = 8,
        variant: str = "fast"
    ):
        """Log Veo generation cost"""
        if variant == "standard":
            cost = duration_seconds * VEO_STANDARD_COST_PER_SEC
        elif variant == "fast":
            cost = duration_seconds * VEO_FAST_COST_PER_SEC
        elif variant == "lite":
            cost = duration_seconds * VEO_LITE_COST_PER_SEC
        else:
            cost = 0

        self.spent += cost
        self.operations.append({
            "type": f"veo_{variant}",
            "cost": cost,
            "timestamp": datetime.utcnow()
        })

        remaining = self.initial_credits - self.spent
        percentage = (self.spent / self.initial_credits) * 100

        logger.info(
            f"Veo {variant}: ${cost:.2f} | "
            f"Spent: ${self.spent:.2f}/{self.initial_credits:.2f} ({percentage:.1f}%) | "
            f"Remaining: ${remaining:.2f}"
        )

        # Alert if approaching limit
        if remaining < 50:  # Less than $50 remaining
            logger.warning(
                f"GCP credits low: ${remaining:.2f} remaining. "
                f"At current rate, credits exhaust in "
                f"{remaining / (self.spent / max(1, len(self.operations))):.0f} videos"
            )

    def estimate_remaining_videos(self) -> int:
        """Estimate how many more videos can be generated"""
        if not self.operations:
            return int(self.initial_credits / 0.80)  # Assume $0.80/video

        avg_cost_per_op = self.spent / len(self.operations)
        remaining = self.initial_credits - self.spent

        return int(remaining / avg_cost_per_op)

    def summary(self) -> Dict:
        """Get usage summary"""
        return {
            "total_budget": self.initial_credits,
            "spent": self.spent,
            "remaining": self.initial_credits - self.spent,
            "percentage_spent": (self.spent / self.initial_credits) * 100,
            "num_operations": len(self.operations),
            "avg_cost_per_op": self.spent / max(1, len(self.operations)),
            "estimated_remaining_videos": self.estimate_remaining_videos()
        }
```

---

## Part 6: Testing

### Local Test (Dry-Run)

```bash
# Set environment variables
export GCP_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
export GCP_GCS_BUCKET=autotube-veo-output
export GCP_PROJECT_ID=autotube-veo-abc123

# Run dry-run
.venv/bin/python3 orchestrator.py --dry-run --topic "AI in 2025"

# Expected output:
# - "Submitting Veo generation: ..."
# - "Generation submitted: projects/XXX/locations/us-central1/operations/..."
# - "Polling... attempt 1/30"
# - "Veo video generated: veo_xxx.mp4 (X MB, ~$X.XX)"
```

### Monitor Cost

```bash
# Check GCP Console for credit usage
# GCP Console → Billing → Costs
# Filter by "Vertex AI" service

# Or check via gcloud CLI
gcloud billing accounts list
gcloud billing budgets list --billing-account=XXXXXXX
```

---

## Part 7: Production Checklist

- [ ] Create GCP project and enable Vertex AI API
- [ ] Create service account with `roles/aiplatform.user` role
- [ ] Generate JSON key and store securely
- [ ] Create GCS bucket in us-central1 region
- [ ] Grant service account permissions on bucket
- [ ] Add GCP credentials to GitHub Secrets
- [ ] Install dependencies: `pip install google-genai google-cloud-storage`
- [ ] Create `agents/gcp_veo_agent.py`
- [ ] Create `agents/gcp_cost_tracker.py`
- [ ] Integrate into `video_agent.py` fallback chain
- [ ] Update `.github/workflows/daily_pipeline.yml` with GCP env vars
- [ ] Test locally with `--dry-run`
- [ ] Test with manual trigger and limited usage
- [ ] Set up billing alert at $250 in GCP Console
- [ ] Document in `CLAUDE.md`
- [ ] Monitor first week for cost burn rate

---

## Part 8: Cost Analysis

**Using Veo Fast ($0.10/second):**

| Days | Videos | Duration | Cost | Remaining |
|------|--------|----------|------|-----------|
| 1-10 | 8-sec (10/day) | 10 days | $8.00 | $292 |
| 11-20 | 8-sec (10/day) | 10 days | $8.00 | $284 |
| 30 | 8-sec (10/day) | 30 days | $24.00 | $276 |
| 41 | 8-sec (10/day) | 41 days | $32.80 | $267.20 |
| 67 | 8-sec (10/day) + 4/day paid | 67 days | ~$300 | Exhausted |

**Post-$300 options:**
1. Switch to Path A (Kling) - free forever
2. Purchase GCP credits as needed
3. Use free alternatives (Ken Burns + Kling)

---

## Part 9: Decision: Which Veo Variant?

| Variant | Cost | Quality | Speed | Best For |
|---------|------|---------|-------|----------|
| **Lite** | $0.40/video | Good | Fast | Budget testing |
| **Fast** | $0.80/video | Good | Standard | **Recommended** |
| **Standard** | $6.00/video | Excellent | Standard | Premium content |

**Recommendation:** Use **Veo Fast** ($0.80/8-sec video). Gets you through full 67-day experiment window with $300 credits while maintaining good quality.

---

## Resources

- [Vertex AI Veo API Docs](https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo)
- [google-genai SDK](https://googleapis.github.io/python-genai/)
- [GCP IAM Roles](https://cloud.google.com/iam/docs/understanding-roles)
- [GCS Python Client](https://cloud.google.com/python/docs/reference/storage/latest)

---

**Next Steps:**
1. Set up GCP project and service account
2. Create GCS bucket
3. Store credentials in GitHub Secrets
4. Implement the code above
5. Test locally with dry-run
6. Deploy to GitHub Actions with conditional (only premium videos)
7. Monitor credit usage daily
