"""
Kokoro-82M text-to-speech (Apache-2.0, runs offline on CPU) — voice for the explainer.

Each shot's line is synthesized separately, so every shot's length is the exact
length of its own narration (picture and voice cannot drift). The model (~350 MB)
downloads once from the kokoro-onnx GitHub release into KOKORO_DIR.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Tuple

import numpy as np
import requests

from config import config

logger = logging.getLogger(__name__)

KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
PAUSE_S = 0.28          # breath after each line
SAMPLE_RATE = 24000


def model_dir() -> Path:
    return Path(os.getenv("KOKORO_DIR", Path.home() / ".cache" / "autotube" / "kokoro"))


def ensure_model() -> Path:
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name in KOKORO_FILES:
        dest = d / name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            continue
        logger.info(f"Downloading Kokoro model file {name} …")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with requests.get(KOKORO_URL + name, stream=True, timeout=(15, 120)) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        tmp.rename(dest)
    return d


class KokoroVoice:
    def __init__(self, voice: str = "", speed: float = 0.0):
        from kokoro_onnx import Kokoro

        d = ensure_model()
        self.tts = Kokoro(str(d / KOKORO_FILES[0]), str(d / KOKORO_FILES[1]))
        self.voice = voice or config.KOKORO_VOICE
        self.speed = speed or config.KOKORO_SPEED

    def synth(self, text: str) -> Tuple[np.ndarray, int]:
        samples, sr = self.tts.create(text, voice=self.voice, speed=self.speed, lang="en-us")
        if samples is None or len(samples) < sr * 0.2:
            raise RuntimeError(f"Kokoro produced no audio for: {text[:60]!r}")
        return samples.astype(np.float32), sr

    def synth_shots(self, texts: List[str], shot_dir: Path) -> Tuple[List[Path], List[float], List[float], int]:
        """Write one WAV per shot (speech + pause). Returns (paths, durations, speech_durations, sr)."""
        import soundfile as sf

        shot_dir.mkdir(parents=True, exist_ok=True)
        paths, durs, speech = [], [], []
        sr = SAMPLE_RATE
        for i, text in enumerate(texts):
            samples, sr = self.synth(text)
            pad = np.zeros(int(sr * PAUSE_S), dtype=np.float32)
            p = shot_dir / f"shot_{i:03d}.wav"
            sf.write(p, np.concatenate([samples, pad]), sr)
            paths.append(p)
            speech.append(len(samples) / sr)
            durs.append((len(samples) + len(pad)) / sr)
            if (i + 1) % 10 == 0 or i + 1 == len(texts):
                logger.info(f"  voice {i+1}/{len(texts)} lines")
        return paths, durs, speech, sr


def concat_and_normalize(paths: List[Path], out_wav: Path) -> None:
    """Concatenate shot WAVs and loudness-normalize to −16 LUFS in a separate pass
    (inside a mix graph loudnorm drops its last ~3 s — found in the POC)."""
    import soundfile as sf

    data = [sf.read(p, dtype="float32")[0] for p in paths]
    sr = sf.info(paths[0]).samplerate
    raw = out_wav.with_name(out_wav.stem + "_raw.wav")
    sf.write(raw, np.concatenate(data), sr)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", str(out_wav)]
    res = subprocess.run(cmd, capture_output=True, timeout=600)
    if res.returncode != 0:
        raise RuntimeError("loudnorm failed: " + res.stderr.decode()[-400:])
    raw.unlink(missing_ok=True)
