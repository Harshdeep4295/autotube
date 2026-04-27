"""
Google Vertex AI Imagen — Text-to-image generation for video backgrounds.

Uses existing GCP service account (same as Veo). No additional setup needed.
"""

import json
import logging
import os
from pathlib import Path

from google.auth import jwt
from google.oauth2 import service_account
import requests

from config import config

logger = logging.getLogger("imagen")


class ImagenImageGenerator:
    """Vertex AI Imagen text-to-image via REST API."""

    def __init__(self):
        self.project_id = config.GCP_PROJECT_ID
        self.region = "us-central1"
        self.token = None
        self.token_exp = 0

        if not self.project_id:
            logger.warning("GCP_PROJECT_ID not set — Imagen unavailable")
            return

        # Load service account
        sa_json_str = os.getenv("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON", "")
        if not sa_json_str:
            logger.warning("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON not set — Imagen unavailable")
            return

        try:
            sa_dict = json.loads(sa_json_str)
            self.credentials = service_account.Credentials.from_service_account_info(
                sa_dict,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            logger.info("✓ Imagen initialized with GCP service account")
        except Exception as e:
            logger.warning(f"Failed to load service account: {e}")

    def _get_token(self) -> str:
        """Get fresh OAuth token for API requests."""
        import time
        if self.token and time.time() < self.token_exp - 300:
            return self.token

        self.token = self.credentials.token
        self.token_exp = time.time() + 3600
        return self.token

    def generate(self, prompt: str, width: int = 1920, height: int = 1080) -> str:
        """
        Generate image from text prompt via Vertex AI Imagen.

        Args:
            prompt: Text description of image
            width: Image width (default 1920)
            height: Image height (default 1080)

        Returns:
            Base64-encoded image or None if failed
        """
        if not self.project_id:
            logger.warning("Imagen not configured")
            return None

        try:
            token = self._get_token()
            url = (
                f"https://{self.region}-aiplatform.googleapis.com/v1/projects/"
                f"{self.project_id}/locations/{self.region}/imageGenerators/"
                f"imagegeneration:predict"
            )

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            body = {
                "instances": [{
                    "prompt": prompt,
                }],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "16:9",
                }
            }

            logger.info(f"Calling Imagen: {prompt[:60]}...")
            resp = requests.post(url, json=body, headers=headers, timeout=300)
            resp.raise_for_status()

            result = resp.json()
            if "predictions" in result and result["predictions"]:
                image_b64 = result["predictions"][0]["bytesBase64Encoded"]
                logger.info(f"✓ Imagen generated image ({len(image_b64)} bytes)")
                return image_b64

            logger.warning(f"Imagen returned empty: {result}")
            return None

        except Exception as e:
            logger.warning(f"Imagen generation failed: {e}")
            return None

    def save_image(self, image_b64: str, output_path: str) -> bool:
        """Save base64 image to file."""
        try:
            import base64
            image_data = base64.b64decode(image_b64)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_data)
            size_kb = len(image_data) // 1024
            logger.info(f"✓ Saved image: {output_path} ({size_kb}KB)")
            return True
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            return False
