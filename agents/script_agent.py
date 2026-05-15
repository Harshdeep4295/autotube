"""
Script Agent
Generates structured video scripts with 4-way fallback: Claude → Gemini → Bedrock → Groq
Hybrid mode: tries Claude first, auto-falls back on quota exhaustion.
All API keys recommended for resilience. Can be overridden via SCRIPT_MODEL_PROVIDER env var.
"""

import json
import logging
import time
from typing import Dict

from config import config
from templates.prompts import SCRIPT_SYSTEM_PROMPT, SCRIPT_USER_PROMPT, SHORTS_USER_PROMPT, get_script_user_prompt

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"title", "description", "tags", "sections", "thumbnail_text"}


class ScriptAgent:
    """
    Generates a structured script JSON from a topic dict.
    Uses Strategy pattern: dispatches to _call_claude() or _call_gemini()
    based on config.SCRIPT_MODEL_PROVIDER.
    """

    def generate(self, topic: Dict) -> Dict:
        """
        4-way fallback script generation: Claude → Gemini → Bedrock → Groq.

        Default behavior (auto mode): Try Claude → Gemini → Bedrock → Groq on quota exhaustion
        Force single provider: Set SCRIPT_MODEL_PROVIDER=claude|gemini|bedrock|groq

        Args:
            topic: dict with keys: topic (str), angle (str), source (str)
        Returns:
            Parsed script dict with keys: title, description, tags, sections, etc.
        Raises:
            RuntimeError: after all retries exhausted on all providers
        """
        provider = config.SCRIPT_MODEL_PROVIDER.lower()
        topic_name = topic.get("topic", "")[:60]

        if provider == "claude":
            logger.info(f"Generating script via Claude (forced) for topic: {topic_name}")
            return self._call_with_retry(self._call_claude, topic)
        elif provider == "gemini":
            logger.info(f"Generating script via Gemini (forced) for topic: {topic_name}")
            return self._call_with_retry(self._call_gemini, topic)
        elif provider == "bedrock":
            logger.info(f"Generating script via Bedrock (forced) for topic: {topic_name}")
            return self._call_with_retry(self._call_bedrock, topic)
        elif provider == "groq":
            logger.info(f"Generating script via Groq (forced) for topic: {topic_name}")
            return self._call_with_retry(self._call_groq, topic)
        elif provider in ("hybrid", "auto"):
            logger.info(f"Generating script via AUTO mode (Claude→Gemini→Bedrock→Groq) for topic: {topic_name}")
            return self._hybrid_generate(topic)
        else:
            raise ValueError(
                f"Unknown SCRIPT_MODEL_PROVIDER='{provider}'. "
                f"Valid values: 'auto', 'hybrid', 'claude', 'gemini', 'bedrock', 'groq'. "
                f"Set the SCRIPT_MODEL_PROVIDER environment variable."
            )

    def _hybrid_generate(self, topic: Dict) -> Dict:
        """4-way fallback: Claude → Gemini → Bedrock → Groq on quota exhaustion."""
        errors = {}

        # Try Claude first
        try:
            return self._call_with_retry(self._call_claude, topic)
        except Exception as exc:
            errors['claude'] = exc
            if not self._is_quota_error(exc):
                raise
            logger.warning(f"Claude quota exhausted: {exc}. Falling back to Gemini…")

        # Try Gemini second
        try:
            return self._call_with_retry(self._call_gemini, topic)
        except Exception as exc:
            errors['gemini'] = exc
            if not self._is_quota_error(exc):
                raise
            logger.warning(f"Gemini quota exhausted: {exc}. Falling back to Bedrock…")

        # Try Bedrock third
        try:
            return self._call_with_retry(self._call_bedrock, topic)
        except Exception as exc:
            errors['bedrock'] = exc
            if not self._is_quota_error(exc):
                raise
            logger.warning(f"Bedrock failed: {exc}. Falling back to Groq…")

        # Try Groq fourth (ultimate fallback)
        try:
            return self._call_with_retry(self._call_groq, topic)
        except Exception as exc:
            errors['groq'] = exc
            logger.error(f"All providers exhausted. Groq error: {exc}")
            raise RuntimeError(
                f"Script generation failed: all 4 providers exhausted. "
                f"Claude: {errors.get('claude')}. "
                f"Gemini: {errors.get('gemini')}. "
                f"Bedrock: {errors.get('bedrock')}. "
                f"Groq: {exc}"
            )

    def _is_quota_error(self, exc: Exception) -> bool:
        """Detect if error is due to quota exhaustion, auth failure, or missing key."""
        error_str = str(exc).lower()
        quota_keywords = [
            "429",
            "quota",
            "rate limit",
            "overloaded",
            "401",
            "403",
            "authentication",
            "invalid api key",
            "not set",
            "too short",
        ]
        return any(keyword in error_str for keyword in quota_keywords)

    # ── Retry wrapper ─────────────────────────────────────────────────────────

    def _call_with_retry(self, fn, topic: Dict) -> Dict:
        last_exc = None
        for attempt in range(config.CLAUDE_RETRIES):
            try:
                raw = fn(topic)
                return self._parse_response(raw)
            except ValueError as exc:
                if "not set" in str(exc).lower():
                    raise RuntimeError(str(exc))
                last_exc = exc
                delay = config.CLAUDE_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"Script attempt {attempt + 1}/{config.CLAUDE_RETRIES} failed: {exc}. "
                    f"Retrying in {delay:.0f}s…"
                )
                time.sleep(delay)
            except Exception as exc:
                last_exc = exc
                delay = config.CLAUDE_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"Script attempt {attempt + 1}/{config.CLAUDE_RETRIES} failed: {exc}. "
                    f"Retrying in {delay:.0f}s…"
                )
                time.sleep(delay)
        raise RuntimeError(
            f"Script generation failed after {config.CLAUDE_RETRIES} attempts. "
            f"Last error: {last_exc}"
        )

    # ── Provider: Claude ──────────────────────────────────────────────────────

    def _call_claude(self, topic: Dict) -> str:
        import anthropic  # lazy import — only needed if using claude
        if not config.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or GitHub Secrets."
            )
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        prompt_template = get_script_user_prompt(config.LANGUAGE, config.IS_SHORTS)
        user_prompt = prompt_template.format(
            topic=topic.get("topic", ""),
            summary=topic.get("angle", ""),
        )
        try:
            message = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                system=SCRIPT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            logger.info(f"[Claude] API request successful ({config.CLAUDE_MODEL})")
            return message.content[0].text
        except Exception as e:
            # Enhance error message with status code if available
            if hasattr(e, 'status_code'):
                logger.error(f"[Claude] API error {e.status_code}: {e}")
            raise

    # ── Provider: Gemini ──────────────────────────────────────────────────────

    def _call_gemini(self, topic: Dict) -> str:
        from google import genai                    # lazy import — google-genai package
        from google.genai import types
        if not config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file or GitHub Secrets for hybrid fallback."
            )
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt_template = get_script_user_prompt(config.LANGUAGE, config.IS_SHORTS)
        user_prompt = prompt_template.format(
            topic=topic.get("topic", ""),
            summary=topic.get("angle", ""),
        )
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SCRIPT_SYSTEM_PROMPT,
                    max_output_tokens=4096,
                    temperature=0.7,
                ),
            )
            logger.info(f"[Gemini] API request successful ({config.GEMINI_MODEL})")
            return response.text
        except Exception as e:
            logger.error(f"[Gemini] API error: {e}")
            raise

    # ── Provider: Groq ────────────────────────────────────────────────────────

    def _call_groq(self, topic: Dict) -> str:
        from openai import OpenAI  # lazy import — groq uses openai SDK
        if not config.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file or GitHub Secrets for 3-way fallback."
            )
        client = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        prompt_template = get_script_user_prompt(config.LANGUAGE, config.IS_SHORTS)
        user_prompt = prompt_template.format(
            topic=topic.get("topic", ""),
            summary=topic.get("angle", ""),
        )
        try:
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=8192,
                temperature=0.5,
            )
            logger.info(f"[Groq] API request successful ({config.GROQ_MODEL})")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[Groq] API error: {e}")
            raise

    # ── Provider: AWS Bedrock ────────────────────────────────────────────────

    _BEDROCK_WORD_COUNT_BOOST = (
        "\n\nABSOLUTE WORD COUNT REQUIREMENT — #1 PRIORITY:\n"
        "You MUST produce at least 1000 total words across all section \"text\" fields.\n"
        "- hook: at least 65 words\n"
        "- context: at least 100 words\n"
        "- main_1 through main_5: at least 140 words EACH\n"
        "- cta: at least 80 words\n"
        "If you produce fewer than 1000 total words, output is REJECTED.\n"
        "Write FULL voiceover narration with specific examples and data — not summaries."
    )

    def _call_bedrock(self, topic: Dict) -> str:
        import boto3  # lazy import — only needed if using bedrock
        if not config.AWS_ACCESS_KEY_ID or not config.AWS_SECRET_ACCESS_KEY:
            raise ValueError(
                "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set. "
                "Add them to your .env file for Bedrock fallback."
            )
        client = boto3.client(
            "bedrock-runtime",
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        )
        prompt_template = get_script_user_prompt(config.LANGUAGE, config.IS_SHORTS)
        user_prompt = prompt_template.format(
            topic=topic.get("topic", ""),
            summary=topic.get("angle", ""),
        )
        system_prompt = SCRIPT_SYSTEM_PROMPT + self._BEDROCK_WORD_COUNT_BOOST
        try:
            response = client.converse(
                modelId=config.BEDROCK_MODEL,
                system=[{"text": system_prompt}],
                messages=[
                    {"role": "user", "content": [{"text": user_prompt}]}
                ],
                inferenceConfig={
                    "maxTokens": 8192,
                    "temperature": 0.7,
                },
            )
            output_text = response["output"]["message"]["content"][0]["text"]
            logger.info(f"[Bedrock] API request successful ({config.BEDROCK_MODEL})")
            return output_text
        except Exception as e:
            logger.error(f"[Bedrock] API error: {e}")
            raise

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> Dict:
        """
        Parses the model's raw text response into a dict.
        Handles two common model quirks:
          1. Wrapping JSON in ```json ... ``` markdown fences
          2. Adding prose before or after the JSON block
        """
        text = raw.strip()

        # Strip markdown code fences (```json\n...\n``` or ```\n...\n```)
        if text.startswith("```"):
            lines = text.split("\n")
            # Drop first line (```json or ```) and last line (```)
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            text = "\n".join(inner).strip()

        # If there's still non-JSON text before the opening brace, strip it
        brace_idx = text.find("{")
        if brace_idx > 0:
            text = text[brace_idx:]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Model returned non-parseable JSON: {exc}\n"
                f"Raw response (first 500 chars): {raw[:500]}"
            )

        missing = REQUIRED_KEYS - data.keys()
        if missing:
            raise ValueError(
                f"Model response missing required keys: {missing}. "
                f"Got keys: {list(data.keys())}"
            )

        if not isinstance(data.get("sections"), list) or len(data["sections"]) < 3:
            raise ValueError(
                f"Model response has too few sections: {len(data.get('sections', []))}. "
                f"Expected at least 3."
            )

        # Validate word count — accept what model produces (Groq limitations)
        actual_words = sum(len(s.get("text", "").split()) for s in data.get("sections", []))
        claimed_words = data.get('total_word_count', actual_words)

        # Update claimed word count to match actual (fix inflated/inaccurate claims)
        data['total_word_count'] = actual_words

        if actual_words < 80:
            logger.warning(f"⚠️  Script critically short ({actual_words} words). Rejecting...")
            raise ValueError(f"Script too short ({actual_words} words, minimum 80 required).")
        else:
            logger.info(
                f"✓ Script accepted: {actual_words} words (Groq limitation — videos will be ~{int(actual_words/150 * 5)} min)"
            )

        logger.info(
            f"✅ Script generated: '{data['title'][:60]}' "
            f"({actual_words} actual words, "
            f"{len(data['sections'])} sections)"
        )
        return data
