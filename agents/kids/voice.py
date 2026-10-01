"""Narration voice for the kids track: Kokoro (default, same engine as the explainer) or Piper (offline fallback)."""

import io
import logging
import wave
from typing import Tuple

import numpy as np

from config import config

logger = logging.getLogger(__name__)


class KidsVoice:
    def __init__(self, engine: str = ""):
        self.engine = (engine or config.KIDS_TTS).lower()
        self._impl = None
        if self.engine == "kokoro":
            try:
                from agents.kokoro_voice import KokoroVoice
                self._impl = KokoroVoice(voice=config.KIDS_KOKORO_VOICE, speed=config.KIDS_KOKORO_SPEED)
            except Exception as e:  # noqa: BLE001
                if not config.PIPER_MODEL:
                    raise
                logger.warning(f"[kids] Kokoro unavailable ({str(e)[:120]}) — falling back to Piper")
                self.engine = "piper"
        if self.engine == "piper":
            from piper import PiperVoice
            if not config.PIPER_MODEL:
                raise RuntimeError("KIDS_TTS=piper needs PIPER_MODEL=/path/to/voice.onnx")
            self._piper = PiperVoice.load(config.PIPER_MODEL)
        self.name = f"{self.engine}:{config.KIDS_KOKORO_VOICE if self.engine == 'kokoro' else config.PIPER_MODEL}"

    def synth(self, text: str) -> Tuple[np.ndarray, int]:
        if self.engine == "kokoro":
            return self._impl.synth(text)
        from piper.config import SynthesisConfig
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            self._piper.synthesize_wav(text, w, syn_config=SynthesisConfig(
                length_scale=1.0 / max(0.5, config.KIDS_KOKORO_SPEED) * 1.05, noise_scale=0.6, noise_w_scale=0.7))
        buf.seek(0)
        with wave.open(buf) as r:
            sr = r.getframerate()
            a = np.frombuffer(r.readframes(r.getnframes()), np.int16).astype(np.float32) / 32768
        if len(a) < sr * 0.2:
            raise RuntimeError(f"Piper produced no audio for: {text[:60]!r}")
        return a, sr
