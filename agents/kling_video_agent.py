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
KLING_API_BASE = "https://api-singapore.klingai.com"  # Updated: new API domain (was api.klingai.com)
JWT_EXPIRATION_SECONDS = 1800  # 30 minutes
POLL_INTERVAL_SECONDS = 5
MAX_POLLING_SECONDS = 300  # 5 minutes timeout (videos take ~60s + exponential backoff delays)
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
            elif response.status_code == 404:
                # Task not found - likely account has no credits or task was rejected
                error_msg = response.text
                self.logger.warning(f"404 response: {error_msg}")
                raise APIError(f"Task not found (404): {error_msg}")
            elif response.status_code == 429:
                raise RateLimitError("Too many requests, retry later")
            elif response.status_code >= 500:
                raise ServiceError(f"Server error: {response.status_code}")

            data = response.json()

            # Handle API-level errors (code can be 200, 0, or "SUCCEED")
            code = data.get("code")
            is_success = code == 200 or code == 0 or code == "SUCCEED"

            if not is_success:
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
            "prompt": prompt[:2500],  # Max 2500 chars
            "negative_prompt": negative_prompt[:2500],
            "duration": min(duration, 15),  # Max 15 seconds
            "aspect_ratio": aspect_ratio,
            "model": "kling-v2.6-pro"
        }

        self.logger.info(f"Submitting Kling generation: {prompt[:100]}...")
        self.logger.debug(f"Request body: {body}")

        data = await self._request("POST", "/v1/videos/text2video", json=body)
        self.logger.info(f"API response data: {json.dumps(data, indent=2)}")

        # Try multiple possible field names for task_id
        task_id = (
            data.get("task_id") or
            data.get("task") or
            data.get("id") or
            data.get("task_id_str") or
            data.get("taskId")
        )

        if not task_id:
            raise APIError(f"No task_id in response. Available keys: {list(data.keys())}")

        self.logger.info(f"Generation submitted: task_id={task_id}")
        return task_id

    async def get_task_status(self, task_id: str) -> Dict:
        """
        Check generation status
        Returns: task_status, videos (if complete), error message (if failed)
        """
        data = await self._request("GET", f"/v1/videos/text2video/{task_id}")

        return {
            "task_id": task_id,
            "task_status": data.get("task_status"),  # submitted, processing, succeed, failed
            "task_status_msg": data.get("task_status_msg"),
            "videos": data.get("task_result", {}).get("videos", []),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at")
        }

    async def poll_until_complete(
        self,
        task_id: str,
        timeout_seconds: int = MAX_POLLING_SECONDS
    ) -> Dict:
        """Poll status until COMPLETED or timeout"""
        import asyncio

        # Brief wait for task to be processed on server
        self.logger.info(f"Polling for task {task_id}...")
        await asyncio.sleep(2)

        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Video generation exceeded {timeout_seconds}s timeout"
                )

            status = await self.get_task_status(task_id)
            task_status = status.get("task_status") or status.get("status")

            if task_status == "succeed":
                self.logger.info(f"Generation complete: {task_id}")
                return status

            elif task_status == "failed":
                error_msg = status.get("task_status_msg", "Unknown error")
                raise GenerationError(f"Generation failed: {error_msg}")

            # Still processing
            self.logger.debug(
                f"Polling {task_id}: status={task_status} "
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
    """High-level video generation orchestrator with async task submission"""

    def __init__(self, storage_dir: str = None):
        self.access_key = os.getenv("KLING_ACCESS_KEY")
        self.secret_key = os.getenv("KLING_SECRET_KEY")

        if not self.access_key or not self.secret_key:
            raise ValueError("KLING_ACCESS_KEY and KLING_SECRET_KEY required")

        self.client = KlingAPIClient(self.access_key, self.secret_key)
        self.logger = logger
        self.storage_dir = storage_dir or str(
            Path(config.VIDEO_CACHE_DIR) / "kling"
        )
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, prompt: str, section_idx: int, duration: int = 5) -> Path:
        """Get cache path for a prompt (shared between submit and check_and_download)"""
        cache_key = hashlib.md5(
            f"kling_{prompt}_{section_idx}_{duration}".encode()
        ).hexdigest()[:12]
        return Path(self.storage_dir) / f"kling_{cache_key}.mp4"

    async def submit(
        self,
        prompt: str,
        section_idx: int,
        duration: int = 5
    ) -> Optional[str]:
        """
        Submit a Kling task and return task_id immediately (fire-and-forget).
        If video is already cached, returns None (no task needed).
        Returns: task_id if submitted, None if cached or failed to submit
        """
        cache_path = self._get_cache_path(prompt, section_idx, duration)

        # Check cache first
        if cache_path.exists() and cache_path.stat().st_size > 100_000:
            self.logger.info(f"[KLING] Using cached video: {cache_path.name}")
            return None  # No task needed

        try:
            # Submit generation task
            task_id = await self.client.submit_text_to_video(
                prompt=prompt,
                duration=duration
            )
            self.logger.info(f"[KLING] Task submitted for section {section_idx}: {task_id}")
            return task_id

        except InsufficientCreditsError:
            self.logger.warning("[KLING] Daily quota exhausted")
            return None

        except ContentPolicyViolation as e:
            self.logger.warning(f"[KLING] Prompt blocked by policy: {e}")
            return None

        except Exception as e:
            self.logger.warning(f"[KLING] Task submission failed: {e}")
            return None

    async def check_and_download(
        self,
        task_id: str,
        prompt: str,
        section_idx: int,
        duration: int = 5,
        timeout_seconds: int = 60
    ) -> Optional[str]:
        """
        Poll Kling task briefly (60s default), download if ready.
        Returns: path to cached video file, or None if not ready / failed
        """
        cache_path = self._get_cache_path(prompt, section_idx, duration)

        try:
            # Brief polling with shorter timeout for render job
            status = await self.client.poll_until_complete(task_id, timeout_seconds=timeout_seconds)

            # Download video
            video_url = status["videos"][0]["url"]
            video_data = await self.client.download_video(video_url)

            # Save to cache
            cache_path.write_bytes(video_data)

            size_mb = len(video_data) / (1024 * 1024)
            self.logger.info(
                f"[KLING] Video downloaded: {cache_path.name} "
                f"({size_mb:.1f}MB)"
            )

            return str(cache_path)

        except asyncio.TimeoutError:
            self.logger.warning(f"[KLING] Task {task_id} not ready after {timeout_seconds}s")
            return None

        except Exception as e:
            self.logger.warning(f"[KLING] Failed to download task {task_id}: {e}")
            return None

    async def generate(
        self,
        prompt: str,
        section_idx: int,
        duration: int = 5
    ) -> Optional[str]:
        """
        Full generate (submit + wait for completion).
        Used only by render job when no prefetch task_id exists.
        Returns: path to cached video file, or None if failed
        """
        cache_path = self._get_cache_path(prompt, section_idx, duration)

        # Check cache
        if cache_path.exists() and cache_path.stat().st_size > 100_000:
            self.logger.info(f"[KLING] Using cached Kling video: {cache_path.name}")
            return str(cache_path)

        try:
            # Submit generation
            task_id = await self.client.submit_text_to_video(
                prompt=prompt,
                duration=duration
            )

            # Poll until complete (full timeout)
            status = await self.client.poll_until_complete(task_id)

            # Download video
            video_url = status["videos"][0]["url"]
            video_data = await self.client.download_video(video_url)

            # Save to cache
            cache_path.write_bytes(video_data)

            size_mb = len(video_data) / (1024 * 1024)
            self.logger.info(
                f"[KLING] Video generated: {cache_path.name} "
                f"({size_mb:.1f}MB)"
            )

            return str(cache_path)

        except InsufficientCreditsError:
            self.logger.warning("[KLING] Daily quota exhausted")
            return None

        except ContentPolicyViolation as e:
            self.logger.warning(f"[KLING] Prompt blocked by policy: {e}")
            return None

        except Exception as e:
            self.logger.warning(f"[KLING] Generation failed: {e}")
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
