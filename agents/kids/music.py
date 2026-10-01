"""A gentle, copyright-free music bed generated in code (plucked arpeggios). Used when data/music has no track."""

import wave
import zlib

import numpy as np

SR = 44100
PROGRESSIONS = [
    [[60, 64, 67, 72], [55, 59, 62, 67], [57, 60, 64, 69], [53, 57, 60, 65]],   # C G Am F
    [[62, 65, 69, 74], [57, 61, 64, 69], [59, 62, 66, 71], [55, 59, 62, 67]],   # Dm A Bm G (bright)
    [[65, 69, 72, 77], [60, 64, 67, 72], [62, 65, 69, 74], [58, 62, 65, 70]],   # F C Dm Bb
]


def _note(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * 3.2) * np.minimum(1, t * 200)
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)) * env


def make_bed(path: str, seconds: float, seed: str = "") -> str:
    h = zlib.crc32(seed.encode())
    chords = PROGRESSIONS[h % len(PROGRESSIONS)]
    bpm = 92 + (h >> 4) % 12
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    beat = 60 / bpm / 2
    total = int((seconds + 2) * SR)
    out = np.zeros(total + SR * 2, np.float32)
    pattern = [0, 1, 2, 3, 2, 1, 2, 3]
    pos = k = 0
    while pos < total:
        ch = chords[(k // 8) % 4]
        s = _note(hz(ch[pattern[k % 8]]), 1.2) * 0.5
        if k % 8 == 0:
            s = s + _note(hz(ch[0] - 12), 1.2) * 0.6
        e = min(len(out), pos + len(s))
        out[pos:e] += s[:e - pos]
        pos += int(beat * SR)
        k += 1
    out = out[:total]
    out /= max(1e-6, np.abs(out).max()) / 0.8
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return path
