"""
Voice Agent
Synthesizes voiceover MP3 from script text using edge-tts (free, no API key).
Falls back to pyttsx3 (offline) if network is unavailable.
"""

import asyncio
import logging
import os
import random
import subprocess
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

        try:
            asyncio.run(self._synthesize_edge_tts(text, output_path))
            logger.info(f"Voiceover saved (edge-tts): {output_path}")
        except Exception as e:
            logger.warning(f"edge-tts failed: {e} — falling back to pyttsx3")
            try:
                self._synthesize_pyttsx3(text, output_path)
                logger.info(f"Voiceover saved (pyttsx3 fallback): {output_path}")
            except Exception as e2:
                raise RuntimeError(f"Both TTS engines failed. pyttsx3 error: {e2}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise RuntimeError(f"Synthesis produced invalid output: {output_path}")

        return output_path

    # ── Edge TTS (primary) ────────────────────────────────────────────────────

    async def _synthesize_edge_tts(self, text: str, output_path: str) -> None:
        import edge_tts

        if config.LANGUAGE != "en":
            voices = config.TTS_VOICES_BY_LANGUAGE.get(config.LANGUAGE, ["en-US-JennyNeural"])
        else:
            voices = list(config.TTS_VOICES.get(config.CHANNEL_NICHE, ["en-US-JennyNeural"]))
        random.shuffle(voices)

        last_error = None
        for voice in voices[:3]:
            try:
                logger.info(f"Trying edge-tts voice: {voice}")
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice,
                    rate=config.TTS_RATE,
                    pitch=config.TTS_PITCH,
                )
                await communicate.save(output_path)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                    return
                last_error = RuntimeError(f"Output file too small with voice {voice}")
            except Exception as e:
                last_error = e
                logger.warning(f"edge-tts voice {voice} failed: {e}")

        raise last_error

    # ── pyttsx3 fallback (offline) ────────────────────────────────────────────

    def _synthesize_pyttsx3(self, text: str, output_path: str) -> None:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 1.0)

        wav_path = output_path.replace(".mp3", ".wav")
        engine.save_to_file(text, wav_path)
        engine.runAndWait()

        if not os.path.exists(wav_path):
            raise RuntimeError("pyttsx3 failed to produce WAV output")

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", wav_path, "-acodec", "libmp3lame", "-b:a", "192k", output_path],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg WAV→MP3 conversion failed: {e.stderr.decode()}") from e
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

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
