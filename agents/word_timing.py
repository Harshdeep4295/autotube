"""
Word timings and caption pages for the explainer.

Timings come from faster-whisper (free, CPU) aligned to the known script words, so
captions highlight the word actually being spoken. If whisper is unavailable or
fails, words are spread over the shot's speech in proportion to their length.

Everything here is pure Python except `WhisperAligner`, so it is unit-tested
without models.
"""

import difflib
import logging
import re
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

Timing = Tuple[float, float]


def norm(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def proportional(words: Sequence[str], speech: float, lead: float = 0.05) -> List[Timing]:
    """Spread words over [lead, speech] by character length (+1 for the gap)."""
    if not words:
        return []
    weights = [len(w) + 1 for w in words]
    total = float(sum(weights))
    span = max(speech - lead, 0.1)
    out, t = [], lead
    for w in weights:
        d = span * w / total
        out.append((round(t, 3), round(t + d, 3)))
        t += d
    return out


def align(script_words: Sequence[str], recognized: Sequence[Tuple[str, float, float]], speech: float) -> List[Timing]:
    """
    Map recognized (word, start, end) onto the script words.

    Matched words take whisper's times; runs of unmatched script words are spread
    proportionally between the surrounding matched times. Result is monotonic.
    """
    n = len(script_words)
    if n == 0:
        return []
    if not recognized:
        return proportional(script_words, speech)
    a = [norm(w) for w in script_words]
    b = [norm(w) for w, _, _ in recognized]
    times: List[Optional[Timing]] = [None] * n
    for blk in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            _, s, e = recognized[blk.b + k]
            times[blk.a + k] = (float(s), float(e))

    # Fill gaps between known anchors.
    i = 0
    while i < n:
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else 0.05
        hi = times[j][0] if j < n else max(speech, lo + 0.1)
        hi = max(hi, lo + 0.05 * (j - i))
        seg = proportional(script_words[i:j], hi - lo, lead=0.0)
        for k, (s, e) in enumerate(seg):
            times[i + k] = (round(lo + s, 3), round(lo + e, 3))
        i = j

    # Enforce monotonic, non-overlapping, inside [0, speech + 0.3].
    out: List[Timing] = []
    prev_end = 0.0
    cap = speech + 0.3
    for s, e in times:  # type: ignore[misc]
        s = min(max(s, prev_end), cap)
        e = min(max(e, s + 0.04), cap)
        out.append((round(s, 3), round(e, 3)))
        prev_end = e
    return out


def emphasis_positions(words: Sequence[str], emphasis: Sequence[str]) -> set:
    """Indexes of words that belong to a whole emphasis phrase occurring in `words`
    (so 'billions of parameters' highlights those three words, not every 'of')."""
    toks = [norm(w) for w in words]
    hits: set = set()
    for phrase in emphasis:
        p = [norm(t) for t in phrase.split() if norm(t)]
        if not p:
            continue
        for i in range(len(toks) - len(p) + 1):
            if toks[i:i + len(p)] == p:
                hits.update(range(i, i + len(p)))
    return hits


def caption_pages(shots: List[Dict], max_words: int = 6, max_chars: int = 38) -> List[Dict]:
    """
    shots: [{start, duration, emphasis, words: [(word, s, e) relative to shot start]}]
    → pages [{start, end, words: [{w, s, e, hi}]}] with absolute times.
    """
    pages: List[Dict] = []
    for shot in shots:
        hi = emphasis_positions([w for w, _, _ in shot["words"]], shot.get("emphasis", []))
        cur: List[Dict] = []
        shot_pages: List[List[Dict]] = []
        for idx, (w, s, e) in enumerate(shot["words"]):
            item = {"w": w, "s": round(shot["start"] + s, 3), "e": round(shot["start"] + e, 3), "hi": idx in hi}
            text_len = len(" ".join(x["w"] for x in cur + [item]))
            if cur and (len(cur) >= max_words or text_len > max_chars):
                shot_pages.append(cur)
                cur = []
            cur.append(item)
            if re.search(r"[.?!;:]$", w) and len(cur) >= 2:
                shot_pages.append(cur)
                cur = []
        if cur:
            shot_pages.append(cur)
        shot_end = shot["start"] + shot["duration"]
        for k, pw in enumerate(shot_pages):
            start = pw[0]["s"]
            end = shot_pages[k + 1][0]["s"] if k + 1 < len(shot_pages) else min(shot_end, pw[-1]["e"] + 0.6)
            pages.append({"start": round(start, 3), "end": round(max(end, start + 0.2), 3), "words": pw})
    return pages


def srt(pages: List[Dict]) -> str:
    def ts(t: float) -> str:
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    lines = []
    for i, p in enumerate(pages, 1):
        lines += [str(i), f"{ts(p['start'])} --> {ts(p['end'])}", " ".join(w["w"] for w in p["words"]), ""]
    return "\n".join(lines)


class WhisperAligner:
    """faster-whisper wrapper. Construct once; `words()` returns [] on any failure."""

    def __init__(self, model: str = "base.en"):
        from faster_whisper import WhisperModel  # optional dependency

        self.model = WhisperModel(model, device="cpu", compute_type="int8")

    def words(self, wav_path: str, prompt: str) -> List[Tuple[str, float, float]]:
        try:
            segments, _ = self.model.transcribe(
                wav_path, language="en", word_timestamps=True, initial_prompt=prompt[:200],
                beam_size=1, vad_filter=False, condition_on_previous_text=False,
            )
            return [(w.word.strip(), float(w.start), float(w.end)) for seg in segments for w in (seg.words or [])]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"whisper failed on {wav_path}: {e}")
            return []


def make_aligner(mode: str) -> Optional["WhisperAligner"]:
    if mode != "whisper":
        return None
    try:
        return WhisperAligner()
    except Exception as e:  # noqa: BLE001 — missing package or model download blocked
        logger.warning(f"faster-whisper unavailable ({str(e)[:120]}) — using proportional word timings")
        return None
