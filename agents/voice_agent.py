"""
Voice Agent
Synthesizes voiceover MP3 from script text using edge-tts (free, no API key).
Falls back to pyttsx3 (offline) if network is unavailable.
"""

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import Dict

from config import config

logger = logging.getLogger(__name__)


class VoiceAgent:
    """Converts script sections to MP3 voiceover using Microsoft Edge TTS."""

    def synthesize(self, script: Dict, output_path: str) -> str:
        """
        Args:
            script: Script dict from ScriptAgent with 'sections' list
            output_path: Full path to save the output MP3
        Returns:
            output_path on success
        Raises:
            RuntimeError: if both edge-tts and pyttsx3 fallback fail
        """
        os.makedirs(Path(output_path).parent, exist_ok=True)
        text = self._build_narration(script)

        logger.info(f"Synthesizing {len(text.split())} words of narration…")

        # Primary: edge-tts (free, high quality, Microsoft neural voices)
        try:
            asyncio.run(self._synthesize_edge_tts(text, output_path))
            logger.info(f"Voiceover saved (edge-tts): {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"edge-tts failed: {e} — falling back to pyttsx3")

        # Fallback: pyttsx3 (offline, lower quality)
        try:
            self._synthesize_pyttsx3(text, output_path)
            logger.info(f"Voiceover saved (pyttsx3 fallback): {output_path}")
            return output_path
        except Exception as e:
            raise RuntimeError(f"Both TTS engines failed. pyttsx3 error: {e}")

    # ── Edge TTS (primary) ────────────────────────────────────────────────────

    def _pick_voice(self) -> str:
        """Pick a random voice from the language-appropriate or niche-appropriate pool."""
        if config.LANGUAGE != "en":
            voices = config.TTS_VOICES_BY_LANGUAGE.get(config.LANGUAGE, ["en-US-JennyNeural"])
        else:
            voices = config.TTS_VOICES.get(config.CHANNEL_NICHE, ["en-US-JennyNeural"])
        voice = random.choice(voices)
        logger.info(f"Selected TTS voice: {voice}")
        return voice

    async def _synthesize_edge_tts(self, text: str, output_path: str) -> None:
        import edge_tts
        voice = self._pick_voice()
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=config.TTS_RATE,
            pitch=config.TTS_PITCH,
        )
        await communicate.save(output_path)

    # ── pyttsx3 fallback (offline) ────────────────────────────────────────────

    def _synthesize_pyttsx3(self, text: str, output_path: str) -> None:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)  # slightly faster than default 200
        engine.setProperty("volume", 1.0)

        # pyttsx3 works better with WAV; save as WAV then rename
        wav_path = output_path.replace(".mp3", ".wav")
        engine.save_to_file(text, wav_path)
        engine.runAndWait()

        # Rename WAV to MP3 (it's still PCM but MoviePy can handle it)
        if os.path.exists(wav_path):
            os.rename(wav_path, output_path)

    # ── Text builder ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_narration(script: Dict) -> str:
        """
        Concatenates all section texts into a single narration string.
        Inserts a brief pause marker (period + space) between sections
        so the TTS engine has natural breathing room.
        """
        sections = script.get("sections", [])
        if not sections:
            raise ValueError("Script has no sections to narrate")

        parts = []
        for section in sections:
            text = section.get("text", "").strip()
            if text:
                parts.append(text)

        # Join with double newline pause cue (edge-tts respects natural pauses)
        return ". ".join(parts)

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def list_voices() -> None:
        """Print available edge-tts voices (useful for customization)."""
        import asyncio
        import edge_tts

        async def _list():
            voices = await edge_tts.list_voices()
            en_voices = [v for v in voices if v["Locale"].startswith("en-")]
            for v in en_voices:
                print(f"  {v['ShortName']:<35} {v['Gender']:<8} {v['Locale']}")

        asyncio.run(_list())
