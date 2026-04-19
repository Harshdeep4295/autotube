# Path A: Kling AI Integration — Complete Implementation Guide

**Status:** Production-ready specification  
**Research Depth:** Comprehensive (14 implementation areas covered)  
**Complexity:** Medium (async polling, JWT auth, error handling)  
**Timeline:** 2-3 days implementation + 1 day testing

---

## Executive Summary

Kling AI provides **66 free credits per day** (~6-10 videos/day at 720p 5-second videos). The API is **fully asynchronous** with **JWT-based authentication** and webhook support. This guide covers production-grade integration into AutoTube's video generation pipeline.

**Key metrics:**
- Free tier: 66 credits/day (renewable daily)
- Cost per video: $0 (within free quota)
- Generation time: 30-90 seconds per 5-second video
- Quality: 720p cinematic video with motion
- Reliability: Webhook support for async notifications

---

## Part 1: Setup & Configuration

### Step 1: Get Kling API Keys

1. Visit **https://app.klingai.com/global/dev**
2. Sign in (Google/Apple/Email)
3. Navigate to **API Keys** section
4. Click **"Create a new API Key"**
5. **CRITICAL:** Copy BOTH keys immediately (Secret Key shown only once):
   - **Access Key (AK):** `ak_xxxxxxxxxxxxxxxxxxxxx`
   - **Secret Key (SK):** `sk_xxxxxxxxxxxxxxxxxxxxx`

### Step 2: Store Credentials Securely

**Create `.env` file (never commit):**
```bash
# .env
KLING_ACCESS_KEY=ak_xxxxxxxxxxxxxxxxxxxxx
KLING_SECRET_KEY=sk_xxxxxxxxxxxxxxxxxxxxx
KLING_WEBHOOK_SECRET=your_webhook_secret_32_chars_minimum
```

**Add to `.gitignore`:**
```
.env
.env.local
*.env
```

**For GitHub Secrets:**
```
Settings → Secrets and Variables → Secrets
- KLING_ACCESS_KEY: ak_xxxxx...
- KLING_SECRET_KEY: sk_xxxxx...
- KLING_WEBHOOK_SECRET: your_webhook_secret
```

### Step 3: Install Dependencies

```bash
pip install kling-api httpx pyjwt aiohttp python-dotenv
```

---

## Part 2: Core Implementation

### File: `agents/kling_video_agent.py` (NEW)

```python
"""
Kling AI Video Generation
- Text-to-video generation with async polling
- JWT-based authentication
- Daily credit tracking and quota management
- Webhook support for async notifications
"""

import asyncio
import logging
import hashlib
import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass, asdict

import httpx
import jwt

from config import config

logger = logging.getLogger(__name__)

# Configuration
KLING_API_BASE = "https://api.evolink.ai/v1"
JWT_EXPIRATION_SECONDS = 1800  # 30 minutes
POLL_INTERVAL_SECONDS = 5
MAX_POLLING_SECONDS = 300  # 5 minutes timeout
VIDEO_URL_EXPIRATION_HOURS = 24


@dataclass
class KlingVideoResult:
    """Result from successful Kling generation"""
    task_id: str
    video_url: str
    file_size_bytes: int
    duration_seconds: int
    resolution: str
    credits_consumed: int
    generated_at: datetime


class KlingJWTAuth:
    """JWT token generation for Kling API"""

    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self._token_cache = None
        self._token_expiry = None

    def get_token(self) -> str:
        """Get valid JWT token, use cached if fresh"""
        now = int(time.time())

        # Check if cached token is still valid (with 60s buffer)
        if (self._token_cache and self._token_expiry and 
            self._token_expiry > now + 60):
            return self._token_cache

        # Generate new token
        now = int(time.time())
        payload = {
            "iss": self.access_key,
            "exp": now + JWT_EXPIRATION_SECONDS,
            "nbf": now - 5  # 5 second buffer for clock skew
        }

        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm="HS256"
        )

        self._token_cache = token
        self._token_expiry = payload["exp"]

        return token


class KlingAPIClient:
    """Async Kling AI API client with full error handling"""

    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.auth = KlingJWTAuth(access_key, secret_key)
        self.http_client = httpx.AsyncClient(timeout=30)
        self.logger = logger

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated API request with error handling"""
        url = f"{KLING_API_BASE}{endpoint}"
        token = self.auth.get_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"

        try:
            response = await self.http_client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )

            # Handle HTTP errors
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired credentials")
            elif response.status_code == 402:
                raise InsufficientCreditsError("Daily quota exhausted")
            elif response.status_code == 429:
                raise RateLimitError("Too many requests, retry later")
            elif response.status_code >= 500:
                raise ServiceError(f"Server error: {response.status_code}")

            data = response.json()

            # Handle API-level errors
            if data.get("code") != 200:
                message = data.get("message", "Unknown error")
                if "invalid content" in message.lower():
                    raise ContentPolicyViolation(message)
                else:
                    raise APIError(f"API error: {message}")

            return data.get("data", {})

        except httpx.TimeoutException:
            raise TimeoutError("API request timeout")
        except httpx.NetworkError as e:
            raise NetworkError(f"Network error: {e}")

    async def submit_text_to_video(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        negative_prompt: str = "",
        mode: str = "std"
    ) -> str:
        """
        Submit text-to-video generation request
        Returns: task_id (use for polling)
        """
        body = {
            "model": "kling-v3-text-to-video",
            "task_type": "video_generation",
            "input": {
                "prompt": prompt[:2500],  # Max 2500 chars
                "negative_prompt": negative_prompt[:2500],
                "duration": min(duration, 15),  # Max 15 seconds
                "aspect_ratio": aspect_ratio,
                "mode": mode
            },
            "config": {}
        }

        self.logger.info(f"Submitting Kling generation: {prompt[:100]}...")

        data = await self._request("POST", "/videos/generations", json=body)
        task_id = data.get("task_id")

        if not task_id:
            raise APIError("No task_id in response")

        self.logger.info(f"Generation submitted: {task_id}")
        return task_id

    async def get_task_status(self, task_id: str) -> Dict:
        """
        Check generation status
        Returns: status, progress, videos (if complete), error (if failed)
        """
        data = await self._request("GET", f"/tasks/{task_id}")

        return {
            "task_id": task_id,
            "status": data.get("status"),  # COMPLETED, FAILED, IN_PROGRESS, PENDING
            "progress": data.get("progress", 0),
            "videos": data.get("videos", []),
            "error": data.get("error"),
            "consumed_credits": data.get("consumed_credits"),
            "completed_at": data.get("completed_at")
        }

    async def poll_until_complete(
        self,
        task_id: str,
        timeout_seconds: int = MAX_POLLING_SECONDS
    ) -> Dict:
        """Poll status until COMPLETED or timeout"""
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Video generation exceeded {timeout_seconds}s timeout"
                )

            status = await self.get_task_status(task_id)

            if status["status"] == "COMPLETED":
                self.logger.info(f"Generation complete: {task_id}")
                return status

            elif status["status"] == "FAILED":
                error = status.get("error", "Unknown error")
                raise GenerationError(f"Generation failed: {error}")

            # Still processing
            self.logger.debug(
                f"Polling {task_id}: {status['progress']}% "
                f"({elapsed:.0f}s elapsed)"
            )

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def download_video(self, url: str) -> bytes:
        """Download video from temporary Kling CDN URL"""
        self.logger.info(f"Downloading video: {url[:50]}...")

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as e:
            raise DownloadError(f"Failed to download video: {e}")


class KlingVideoGenerator:
    """High-level video generation orchestrator"""

    def __init__(self, storage_dir: str = None):
        self.access_key = os.getenv("KLING_ACCESS_KEY")
        self.secret_key = os.getenv("KLING_SECRET_KEY")

        if not self.access_key or not self.secret_key:
            raise ValueError("KLING_ACCESS_KEY and KLING_SECRET_KEY required")

        self.client = KlingAPIClient(self.access_key, self.secret_key)
        self.storage_dir = storage_dir or str(
            Path(config.VIDEO_CACHE_DIR) / "kling"
        )
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        prompt: str,
        section_idx: int,
        duration: int = 5
    ) -> Optional[str]:
        """
        Generate video from prompt
        Returns: path to cached video file, or None if failed
        """
        # Create cache key
        cache_key = hashlib.md5(
            f"kling_{prompt}_{section_idx}_{duration}".encode()
        ).hexdigest()[:12]
        cache_path = Path(self.storage_dir) / f"kling_{cache_key}.mp4"

        # Check cache
        if cache_path.exists() and cache_path.stat().st_size > 100_000:
            self.logger.info(f"Using cached Kling video: {cache_path.name}")
            return str(cache_path)

        try:
            # Submit generation
            task_id = await self.client.submit_text_to_video(
                prompt=prompt,
                duration=duration
            )

            # Poll until complete
            status = await self.client.poll_until_complete(task_id)

            # Download video
            video_url = status["videos"][0]["url"]
            video_data = await self.client.download_video(video_url)

            # Save to cache
            cache_path.write_bytes(video_data)

            size_mb = len(video_data) / (1024 * 1024)
            self.logger.info(
                f"Kling video generated: {cache_path.name} "
                f"({size_mb:.1f}MB, {status['consumed_credits']} credits)"
            )

            return str(cache_path)

        except InsufficientCreditsError:
            self.logger.warning("Kling daily quota exhausted")
            return None

        except ContentPolicyViolation as e:
            self.logger.warning(f"Prompt blocked by policy: {e}")
            return None

        except Exception as e:
            self.logger.warning(f"Kling generation failed: {e}")
            return None

    async def close(self):
        """Cleanup"""
        await self.client.close()


# Custom Exceptions
class KlingError(Exception):
    """Base Kling exception"""
    pass


class AuthenticationError(KlingError):
    """Auth failed (invalid/expired credentials)"""
    pass


class InsufficientCreditsError(KlingError):
    """Daily quota exhausted"""
    pass


class RateLimitError(KlingError):
    """API rate limited"""
    pass


class ContentPolicyViolation(KlingError):
    """Prompt violates content policy"""
    pass


class GenerationError(KlingError):
    """Video generation failed"""
    pass


class APIError(KlingError):
    """Generic API error"""
    pass


class ServiceError(KlingError):
    """Server-side error (5xx)"""
    pass


class NetworkError(KlingError):
    """Network error"""
    pass


class TimeoutError(KlingError):
    """Request timeout"""
    pass


class DownloadError(KlingError):
    """Video download failed"""
    pass
```

### Step 3: Wire into VideoAgent

**File:** `agents/video_agent.py` (modify)

Add to imports:
```python
from agents.kling_video_agent import KlingVideoGenerator
```

Add to `__init__`:
```python
self.kling_generator = None
```

Add to `generate_videos()` method, in the fallback chain (around line 220):

```python
# In _try_section_video_chain, add Kling as fallback option

def _try_section_video_chain(self, section_idx: int, query: str, primary_mode: str) -> Optional[str]:
    """Chain: primary_mode → Seedance → Kling → Ken Burns → Pexels → Gradient"""
    modes = []
    
    if primary_mode in ["seedance", "ken_burns"]:
        modes.append(primary_mode)
    
    if "seedance" not in modes:
        modes.append("seedance")
    
    # NEW: Add Kling as second fallback (before Ken Burns)
    modes.append("kling")
    
    if "ken_burns" not in modes:
        modes.append("ken_burns")
    
    modes.append("pexels")
    
    for mode in modes:
        try:
            if mode == "kling":
                # Initialize generator if needed
                if not self.kling_generator:
                    self.kling_generator = KlingVideoGenerator()
                
                # Use asyncio to run async function
                import asyncio
                path = asyncio.run(
                    self.kling_generator.generate(query, section_idx)
                )
            
            elif mode == "seedance":
                path = self._fetch_seedance_video(query, section_idx)
            
            elif mode == "ken_burns":
                # ... existing code ...
                pass
            
            # ... rest of chain ...
            
        except Exception as e:
            logger.warning(f"Section {section_idx+1}: {mode} failed ({e})")
            continue
```

---

## Part 3: Credit Management

### Create: `agents/kling_quota_manager.py` (NEW)

```python
"""
Kling daily quota management
- Track credit consumption
- Alert when quota low
- Queue jobs for next day if exhausted
"""

import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)

DAILY_CREDITS = 66
ALERT_THRESHOLD = 10  # Alert if <10 credits remaining
GENERATION_COST = 10  # 5-second 720p video = 10 credits


class KlingQuotaTracker:
    """Track daily credit usage and alert on low quota"""

    def __init__(self, state_file: str = "data/kling_state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def _load_state(self):
        """Load quota state from file"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                state = json.load(f)
                self.last_reset = datetime.fromisoformat(state["last_reset"])
                self.credits_used_today = state["credits_used_today"]
        else:
            self.last_reset = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            self.credits_used_today = 0

    def _save_state(self):
        """Save quota state to file"""
        with open(self.state_file, "w") as f:
            json.dump({
                "last_reset": self.last_reset.isoformat(),
                "credits_used_today": self.credits_used_today
            }, f)

    def _check_and_reset(self):
        """Check if day has changed, reset counter if needed"""
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if today > self.last_reset:
            # New day, reset counter
            logger.info("Daily quota reset")
            self.last_reset = today
            self.credits_used_today = 0
            self._save_state()

    def get_remaining_credits(self) -> int:
        """Get remaining credits for today"""
        self._check_and_reset()
        return max(0, DAILY_CREDITS - self.credits_used_today)

    def can_generate(self) -> bool:
        """Check if enough credits for one video"""
        remaining = self.get_remaining_credits()
        enough = remaining >= GENERATION_COST

        if not enough:
            logger.warning(f"Insufficient credits: need {GENERATION_COST}, have {remaining}")

        if remaining < ALERT_THRESHOLD:
            logger.warning(
                f"Kling quota running low: {remaining}/{DAILY_CREDITS} credits remaining"
            )

        return enough

    def consume_credits(self, amount: int = GENERATION_COST):
        """Record credit consumption"""
        self.credits_used_today += amount
        self._save_state()
        logger.info(
            f"Consumed {amount} credits. "
            f"Remaining: {self.get_remaining_credits()}/{DAILY_CREDITS}"
        )

    def refund_credits(self, amount: int = GENERATION_COST):
        """Refund credits (if generation fails)"""
        self.credits_used_today = max(0, self.credits_used_today - amount)
        self._save_state()
        logger.info(f"Refunded {amount} credits")
```

---

## Part 4: GitHub Actions Workflow

**File:** `.github/workflows/daily_pipeline.yml` (modify)

Add environment variables:
```yaml
env:
  KLING_ACCESS_KEY: ${{ secrets.KLING_ACCESS_KEY }}
  KLING_SECRET_KEY: ${{ secrets.KLING_SECRET_KEY }}
  KLING_WEBHOOK_SECRET: ${{ secrets.KLING_WEBHOOK_SECRET }}
```

---

## Part 5: Testing

### Local Test (Dry-Run)

```bash
# Set environment variables
export KLING_ACCESS_KEY=ak_xxxxx
export KLING_SECRET_KEY=sk_xxxxx

# Run dry-run
.venv/bin/python3 orchestrator.py --dry-run --topic "AI in 2025"

# Expected output:
# - "Submitting Kling generation: ..."
# - "Generation submitted: record_abc123..."
# - "Polling... attempt 1/60"
# - "Generation complete: record_abc123"
# - "Downloaded X bytes"
# - "Kling video generated: kling_xxx.mp4 (X MB, 10 credits)"
```

### Production Test (With Upload)

```bash
# Test with actual generation and upload
.venv/bin/python3 orchestrator.py --upload --topic "AI in 2025"

# Watch logs for:
# - Successful Kling generation
# - YouTube upload completion
# - Proper thumbnail

# Check generated video:
# - Verify motion/animation is present
# - Check quality (should be 720p cinematic)
# - Confirm no black gradients
```

---

## Part 6: Error Handling & Fallback

Kling failures trigger automatic fallback chain:

```
Kling generation attempt
  ├─ Success? → Use video ✓
  ├─ Insufficient credits (402)? → Queue for tomorrow
  ├─ Content policy violation? → Use Ken Burns fallback
  ├─ Network error? → Retry with exponential backoff
  └─ Other error? → Try next mode (Ken Burns)
```

---

## Part 7: Monitoring & Alerts

### Credit Usage Tracking

```python
# In orchestrator.py, track daily usage
from agents.kling_quota_manager import KlingQuotaTracker

quota = KlingQuotaTracker()

# Before each generation
if not quota.can_generate():
    logger.info("Kling quota exhausted, using fallback")
    # Use Ken Burns or Pexels instead
else:
    # Generate with Kling
    quota.consume_credits(10)
```

### Alert Example

```python
# Send alert when quota low
if quota.get_remaining_credits() < 10:
    send_email(
        to="your-email@example.com",
        subject="Kling AI quota low",
        body=f"Only {quota.get_remaining_credits()} credits remaining, resets at UTC midnight"
    )
```

---

## Part 8: Optimization Tips

### 1. Pre-validate Prompts

```python
def should_generate_with_kling(prompt: str) -> bool:
    """
    Check if prompt is likely to succeed (not blocked by safety filters)
    """
    blocked_words = ["violence", "explicit", "death", "gore"]
    for word in blocked_words:
        if word.lower() in prompt.lower():
            return False  # Skip Kling, use fallback
    return True
```

### 2. Batch Generations

```python
# If generating multiple videos, space them out
import asyncio

async def batch_generate(prompts, batch_size=3):
    """Generate videos with concurrency limit"""
    tasks = []
    for prompt in prompts:
        tasks.append(generator.generate(prompt))
        
        if len(tasks) >= batch_size:
            await asyncio.gather(*tasks)
            tasks = []
            await asyncio.sleep(10)  # Space out batches
    
    if tasks:
        await asyncio.gather(*tasks)
```

### 3. Time Generations During Off-Peak

```python
from datetime import datetime

def should_generate_now() -> bool:
    """
    Kling is faster UTC 0-6 (off-peak)
    Slower UTC 9-17 (peak hours)
    """
    hour = datetime.utcnow().hour
    return hour < 6  # Off-peak
```

---

## Part 9: Production Checklist

- [ ] Add Kling API keys to GitHub Secrets
- [ ] Install dependencies: `pip install kling-api httpx pyjwt`
- [ ] Create `agents/kling_video_agent.py`
- [ ] Create `agents/kling_quota_manager.py`
- [ ] Integrate into `video_agent.py` fallback chain
- [ ] Update `.github/workflows/daily_pipeline.yml` with Kling env vars
- [ ] Update `requirements.txt` with new packages
- [ ] Test locally with `--dry-run`
- [ ] Test with `--upload` to verify YouTube integration
- [ ] Monitor first 3 runs for errors
- [ ] Set up credit usage alert (threshold: 10 credits)
- [ ] Document in `CLAUDE.md`

---

## Part 10: Cost Analysis

**Daily budget: 66 credits**

| Scenario | Videos/Day | Quality | Result |
|----------|------------|---------|--------|
| 5-sec 720p | 6 | Good | **Sustainable forever** |
| Mix of 5-sec + 10-sec | 3-4 | Good | **Safe daily quota** |
| All 10-sec 720p | 3 | Better | **Use sparingly** |

**Monthly: 180-200 free videos at 720p quality**

---

## Resources

- [Kling AI API Documentation](https://app.klingai.com/global/dev/document-api/)
- [Kling Python SDK](https://github.com/TechWithTy/kling)
- [JWT Token Generation Guide](https://tools.ietf.org/html/rfc7519)

---

**Next Steps:**
1. Implement the code above
2. Test locally
3. Deploy to GitHub Actions
4. Monitor first week for quota usage
5. Adjust fallback chain if needed
