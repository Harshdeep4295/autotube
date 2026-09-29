"""
Free-tier LLM client: Gemini free tier → Groq free tier.

One call = `complete(system, user)` → raw text. Models are tried in the order of
config.GEMINI_FREE_MODELS then config.GROQ_FREE_MODELS. A rate-limit (429) is
retried with backoff on the same model; any other failure moves to the next model
(free tiers retire models without notice — Groq dropped Llama in Aug 2026).
A 404 that names a replacement ("use models/X") is followed automatically, and the
model that worked is tried first on later calls in the same run. Transient overload
errors (503 UNAVAILABLE / "high demand", 500) get a short backoff retry too.

Gemini 3.x models "think" before answering and those tokens count against
max_output_tokens, which truncated long JSON answers. Thinking is capped
(GEMINI_THINKING_LEVEL, default "low"); a model that rejects the setting is retried
without it, and a MAX_TOKENS finish is logged so cut-off JSON is easy to spot.
"""

import logging
import re
import time
from typing import Callable, List, Optional, Tuple

from config import config

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "resource_exhausted" in s or "quota" in s


def _is_transient(exc: Exception) -> bool:
    s = str(exc).lower()
    return ("503" in s or "unavailable" in s or "high demand" in s or "overloaded" in s
            or "500 internal" in s or "deadline" in s)


def _retry_after(exc: Exception, default: float) -> float:
    m = re.search(r"retry[^0-9]{0,20}(\d+(?:\.\d+)?)\s*s", str(exc), re.I)
    return min(float(m.group(1)) + 1, 90) if m else default


def _successor(exc: Exception) -> Optional[str]:
    """Replacement model named in a 'model no longer available' error, if any."""
    s = str(exc)
    if "no longer available" not in s and "not found" not in s.lower():
        return None
    m = re.search(r"use (?:the )?models/([A-Za-z0-9][\w.\-]*[A-Za-z0-9])", s)
    return m.group(1) if m else None


class FreeLLM:
    def __init__(self, max_rate_limit_retries: int = 3):
        self.max_rl = max_rate_limit_retries
        self.last_model: Optional[str] = None
        self._preferred: Optional[Tuple[str, str, Callable]] = None
        self._no_thinking_cfg: set = set()   # models that rejected thinking_config
        self.max_transient = 2

    # Providers ---------------------------------------------------------------

    def _gemini(self, model: str, system: str, user: str, max_tokens: int, temperature: float) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        level = (config.GEMINI_THINKING_LEVEL or "").strip().lower()

        def call(with_thinking: bool):
            kw = dict(system_instruction=system, max_output_tokens=max_tokens, temperature=temperature,
                      response_mime_type="application/json")
            if with_thinking:
                kw["thinking_config"] = types.ThinkingConfig(thinking_level=level)
            return client.models.generate_content(model=model, contents=user,
                                                  config=types.GenerateContentConfig(**kw))

        use_thinking = bool(level) and level != "default" and model not in self._no_thinking_cfg
        try:
            resp = call(use_thinking)
        except Exception as e:  # noqa: BLE001
            if use_thinking and "think" in str(e).lower() and ("400" in str(e) or "invalid" in str(e).lower()):
                logger.info(f"[LLM] gemini:{model} rejected thinking_level={level} — retrying without it")
                self._no_thinking_cfg.add(model)
                resp = call(False)
            else:
                raise
        try:
            finish = str(resp.candidates[0].finish_reason or "")
        except (AttributeError, IndexError, TypeError):
            finish = ""
        if "MAX_TOKENS" in finish:
            logger.warning(f"[LLM] gemini:{model} hit max_output_tokens={max_tokens} — answer may be cut off")
        return resp.text or ""

    def _groq(self, model: str, system: str, user: str, max_tokens: int, temperature: float) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=config.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""

    def chain(self) -> List[Tuple[str, str, Callable]]:
        out = []
        if config.GEMINI_API_KEY:
            out += [("gemini", m, self._gemini) for m in config.GEMINI_FREE_MODELS]
        if config.GROQ_API_KEY:
            out += [("groq", m, self._groq) for m in config.GROQ_FREE_MODELS]
        if not config.FREE_ONLY and config.ANTHROPIC_API_KEY:
            out.append(("claude", config.CLAUDE_MODEL, self._claude))
        return out

    def _claude(self, model: str, system: str, user: str, max_tokens: int, temperature: float) -> str:
        import anthropic  # only reachable with FREE_ONLY=false

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                     messages=[{"role": "user", "content": user}], temperature=temperature)
        return msg.content[0].text

    # Public ------------------------------------------------------------------

    def complete(self, system: str, user: str, max_tokens: int = 8192, temperature: float = 0.6) -> str:
        chain = self.chain()
        if not chain:
            raise LLMError("No free LLM configured: set GEMINI_API_KEY and/or GROQ_API_KEY.")
        # Start with the model that worked last time (saves dead-model calls on every chapter).
        if self._preferred:
            chain = [self._preferred] + [c for c in chain if c[:2] != self._preferred[:2]]
        errors = []
        tried = set()
        i = 0
        while i < len(chain):
            provider, model, fn = chain[i]
            i += 1
            if (provider, model) in tried:
                continue
            tried.add((provider, model))
            for attempt in range(self.max_rl + 1):
                try:
                    text = fn(model, system, user, max_tokens, temperature)
                    if not text.strip():
                        raise LLMError("empty response")
                    self.last_model = f"{provider}:{model}"
                    self._preferred = (provider, model, fn)
                    logger.info(f"[LLM] {self.last_model} ok ({len(text)} chars)")
                    return text
                except Exception as e:  # noqa: BLE001 — any provider error → next option
                    if _is_transient(e) and not _is_rate_limit(e) and attempt < self.max_transient:
                        wait = 8 * (attempt + 1)
                        logger.warning(f"[LLM] {provider}:{model} overloaded — retry in {wait}s")
                        time.sleep(wait)
                        continue
                    if _is_rate_limit(e) and attempt < self.max_rl:
                        wait = _retry_after(e, 10 * (attempt + 1))
                        logger.warning(f"[LLM] {provider}:{model} rate-limited — retry in {wait:.0f}s")
                        time.sleep(wait)
                        continue
                    logger.warning(f"[LLM] {provider}:{model} failed: {str(e)[:200]}")
                    errors.append(f"{provider}:{model}: {str(e)[:120]}")
                    # Retired model: the error names its replacement ("use models/gemini-3.5-flash-lite").
                    successor = _successor(e)
                    if successor and (provider, successor) not in tried:
                        logger.info(f"[LLM] {provider}:{model} is retired — trying suggested {successor}")
                        chain.insert(i, (provider, successor, fn))
                    break
        raise LLMError("All free LLM options failed — " + " | ".join(errors))
