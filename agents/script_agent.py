"""
Script Agent
Generates structured video scripts via Claude or Gemini based on config.
Provider is selected by SCRIPT_MODEL_PROVIDER env var (default: "claude").
Switching providers requires no code change — only an env var update.
"""

import json
import logging
import time
from typing import Dict

from config import config
from templates.prompts import SCRIPT_SYSTEM_PROMPT, SCRIPT_USER_PROMPT

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
        Args:
            topic: dict with keys: topic (str), angle (str), source (str)
        Returns:
            Parsed script dict with keys: title, description, tags, sections,
            thumbnail_text, thumbnail_subtext, pexels_search_query, total_word_count
        Raises:
            RuntimeError: after all retries are exhausted
            ValueError: if SCRIPT_MODEL_PROVIDER is not recognized
        """
        provider = config.SCRIPT_MODEL_PROVIDER.lower()
        logger.info(f"Generating script via provider='{provider}' for topic: {topic.get('topic', '')[:60]}")

        if provider == "claude":
            return self._call_with_retry(self._call_claude, topic)
        elif provider == "gemini":
            return self._call_with_retry(self._call_gemini, topic)
        else:
            raise ValueError(
                f"Unknown SCRIPT_MODEL_PROVIDER='{provider}'. "
                f"Valid values: 'claude', 'gemini'. "
                f"Set the SCRIPT_MODEL_PROVIDER environment variable."
            )

    # ── Retry wrapper ─────────────────────────────────────────────────────────

    def _call_with_retry(self, fn, topic: Dict) -> Dict:
        last_exc = None
        for attempt in range(config.CLAUDE_RETRIES):
            try:
                raw = fn(topic)
                return self._parse_response(raw)
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
        user_prompt = SCRIPT_USER_PROMPT.format(
            topic=topic.get("topic", ""),
            summary=topic.get("angle", ""),
        )
        message = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            system=SCRIPT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    # ── Provider: Gemini ──────────────────────────────────────────────────────

    def _call_gemini(self, topic: Dict) -> str:
        from google import genai                    # lazy import — google-genai package
        from google.genai import types
        if not config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file or set SCRIPT_MODEL_PROVIDER=claude to use Claude instead."
            )
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        user_prompt = SCRIPT_USER_PROMPT.format(
            topic=topic.get("topic", ""),
            summary=topic.get("angle", ""),
        )
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SCRIPT_SYSTEM_PROMPT,
                max_output_tokens=4096,
                temperature=0.7,
            ),
        )
        return response.text

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

        logger.info(
            f"Script generated: '{data['title'][:60]}' "
            f"({data.get('total_word_count', '?')} words, "
            f"{len(data['sections'])} sections)"
        )
        return data
