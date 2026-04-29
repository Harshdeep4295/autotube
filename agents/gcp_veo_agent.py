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

from google import genai
from google.oauth2 import service_account
from google.cloud import storage as gcs
from google.api_core import exceptions as gcp_exceptions

from config import config

logger = logging.getLogger(__name__)

# Configuration
VEO_MODEL = "veo-3.1-generate-001"
VEO_REGION = "us-central1"
VEO_DURATION = 8  # seconds (max for standard)
VEO_RESOLUTION = "1080p"
VEO_ASPECT_RATIO = "16:9"
POLL_INTERVAL_SECONDS = 20
MAX_POLLING_SECONDS = 600  # 10 minutes (Veo takes 2-4 min)


class VeoAuthenticator:
    """GCP service account authentication"""

    def __init__(self, service_account_json: str, project_id: str):
        sa_dict = json.loads(service_account_json)
        self.credentials = service_account.Credentials.from_service_account_info(
            sa_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.project_id = project_id

    def get_credentials(self):
        return self.credentials

    def get_gcs_client(self):
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

        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=gcs_region,
            credentials=self.credentials
        )

        self.logger = logger

    async def submit_text_to_video(
        self,
        prompt: str,
        duration_seconds: int = VEO_DURATION
    ):
        """Submit text-to-video request. Returns operation object for polling."""
        from google.genai import types

        gcs_output_uri = f"gs://{self.gcs_bucket}/veo_output/"

        self.logger.info(f"Submitting Veo generation: {prompt[:80]}...")

        try:
            operation = self.client.models.generate_videos(
                model=VEO_MODEL,
                source=types.GenerateVideosSource(
                    prompt=prompt[:2000]
                ),
                config=types.GenerateVideosConfig(
                    output_gcs_uri=gcs_output_uri,
                    duration_seconds=duration_seconds,
                    aspect_ratio=VEO_ASPECT_RATIO,
                    resolution=VEO_RESOLUTION,
                    quality_tier="FAST",
                    person_generation="dont_allow",
                ),
            )

            self.logger.info(f"Generation submitted: {operation.name}")
            return operation  # Return the operation object, not just the name

        except gcp_exceptions.PermissionDenied:
            raise PermissionError("Missing IAM role: roles/aiplatform.user")
        except gcp_exceptions.NotFound:
            raise ValueError("Invalid project ID or bucket name")
        except Exception as e:
            raise Exception(f"Failed to submit generation: {e}")

    async def poll_operation(
        self,
        operation,
        timeout_seconds: int = MAX_POLLING_SECONDS
    ) -> Dict:
        """Poll operation until complete. Expects operation object from submit_text_to_video."""
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Video generation exceeded {timeout_seconds}s timeout"
                )

            self.logger.debug(f"Polling operation ({elapsed:.0f}s elapsed)")

            # Poll using google-genai client.operations.get() with the operation object
            operation = self.client.operations.get(operation=operation)

            self.logger.debug(f"Poll response: done={operation.done}")

            if operation.done:
                if operation.error:
                    error_msg = operation.error.message or str(operation.error)
                    self.logger.error(f"Generation failed: {error_msg}")
                    raise Exception(f"Generation error: {error_msg}")

                self.logger.info(f"✅ Generation complete")
                return {
                    "operation_name": operation.name,
                    "result": operation.result,
                    "duration": elapsed
                }

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def download_from_gcs(
        self,
        gcs_uri: str,
        local_path: Path
    ) -> Tuple[Path, int]:
        """Download video from GCS to local storage."""
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        parts = gcs_uri[5:].split("/", 1)
        bucket_name = parts[0]
        blob_path = parts[1]

        self.logger.info(f"Downloading from GCS: {gcs_uri}")

        try:
            bucket = self.gcs_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.download_to_filename(str(local_path))

            file_size = local_path.stat().st_size
            self.logger.info(
                f"Downloaded: {local_path.name} ({file_size / 1024 / 1024:.1f}MB)"
            )

            return local_path, file_size

        except Exception as e:
            raise Exception(f"Failed to download from GCS: {e}")


class VeoVideoGenerator:
    """High-level video generation orchestrator"""

    def __init__(self):
        service_account_json = os.getenv("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON")
        project_id = os.getenv("GCP_PROJECT_ID")
        gcs_bucket = os.getenv("GCP_GCS_BUCKET")

        if not all([service_account_json, project_id, gcs_bucket]):
            raise ValueError(
                "AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON, GCP_PROJECT_ID, GCP_GCS_BUCKET required"
            )

        self.client = VeoAPIClient(
            service_account_json=service_account_json,
            project_id=project_id,
            gcs_bucket=gcs_bucket
        )

        self.storage_dir = Path(config.VIDEO_CACHE_DIR) / "gcp_veo"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    async def generate(
        self,
        prompt: str,
        section_idx: int,
        duration: int = 8,
        retry_count: int = 0
    ) -> Optional[str]:
        """Generate video from prompt. Returns path to cached video file, or None if failed.
        No retries — single attempt only. Reduces costs to $0.80 per section max.
        """
        cache_key = hashlib.md5(
            f"veo_{prompt}_{section_idx}_{duration}".encode()
        ).hexdigest()[:12]
        cache_path = self.storage_dir / f"veo_{cache_key}.mp4"

        if cache_path.exists() and cache_path.stat().st_size > 1_000_000:
            self.logger.info(f"Using cached Veo video: {cache_path.name}")
            return str(cache_path)

        try:
            start_time = time.time()

            operation = await self.client.submit_text_to_video(
                prompt=prompt,
                duration_seconds=duration
            )

            result = await self.client.poll_operation(operation)

            generated_videos = result["result"].generated_videos
            if not generated_videos:
                self.logger.error(f"No videos in response — falling back to gradient")
                return None

            gcs_uri = generated_videos[0].video.uri

            await self.client.download_from_gcs(gcs_uri, cache_path)

            generation_time = time.time() - start_time
            size_mb = cache_path.stat().st_size / (1024 * 1024)
            cost_per_sec = 0.10  # Veo Fast variant
            estimated_cost = duration * cost_per_sec

            self.logger.info(
                f"Veo video generated: {cache_path.name} "
                f"({size_mb:.1f}MB, {generation_time:.0f}s, "
                f"~${estimated_cost:.2f})"
            )

            return str(cache_path)

        except TimeoutError:
            self.logger.warning(f"Veo generation timeout (>10 minutes)")
            return None

        except Exception as e:
            self.logger.warning(f"Veo generation failed: {e}", exc_info=True)
            return None
