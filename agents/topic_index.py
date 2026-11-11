"""
Duplicate check by meaning: each topic or title becomes a vector (BAAI/bge-small-en-v1.5 through
fastembed, small and free, runs on the CPU), and two topics whose vectors are closer than
TOPIC_DUP_SIMILARITY are the same video. This catches what the word rules miss ("What is a
computer chip?" vs "What is a Chip?" 0.91, "How does a chatbot answer you?" vs "How does a chatbot
talk?" 0.92). Kids questions use TOPIC_DUP_SIMILARITY (0.85). Explainer topics are all about AI
tools and sit close together, so they use EXPLAINER_DUP_SIMILARITY (0.93, near-identical wording).

Vectors are kept in data/topic_index.npz (text → vector), so a daily run only embeds new texts.
If the model cannot load, every call returns None and the word rules still apply.
"""

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from config import config

logger = logging.getLogger(__name__)

MODEL = "BAAI/bge-small-en-v1.5"
_model = None
_broken = False
_vectors: Dict[str, np.ndarray] = {}
_loaded = False


def _key(text: str) -> str:
    return " ".join(str(text).split()).strip()


def _load_file() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    path = Path(config.TOPIC_INDEX_FILE)
    if not path.exists():
        return
    try:
        data = np.load(path, allow_pickle=False)
        for t, v in zip(data["texts"], data["vectors"]):
            _vectors[str(t)] = v.astype(np.float32)
    except Exception as e:  # noqa: BLE001 — rebuilt on the next save
        logger.warning(f"[index] could not read {path}: {str(e)[:120]}")


def _embedder():
    global _model, _broken
    if _model is None and not _broken:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(MODEL, cache_dir=str(Path(".cache") / "fastembed"))
        except Exception as e:  # noqa: BLE001 — the word rules still apply
            _broken = True
            logger.warning(f"[index] embedding model unavailable ({str(e)[:150]}) — word rules only")
    return _model


def enabled() -> bool:
    return config.TOPIC_INDEX and _embedder() is not None


def vectors(texts: Iterable[str]) -> Optional[np.ndarray]:
    """Unit vectors for `texts` (cached), or None when the model is unavailable."""
    keys = [_key(t) for t in texts]
    if not config.TOPIC_INDEX:
        return None
    _load_file()
    missing = list(dict.fromkeys(k for k in keys if k and k not in _vectors))
    if missing:
        model = _embedder()
        if model is None:
            return None
        try:
            for k, v in zip(missing, model.embed(missing)):
                v = np.asarray(v, dtype=np.float32)
                _vectors[k] = v / (np.linalg.norm(v) or 1.0)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[index] embedding failed: {str(e)[:150]}")
            return None
    if not keys:
        return np.zeros((0, 384), dtype=np.float32)
    return np.stack([_vectors.get(k, np.zeros(384, dtype=np.float32)) for k in keys])


def similar(text: str, others: List[str], k: int = 3) -> Optional[List[Tuple[float, str]]]:
    """The `k` closest of `others` to `text` as (similarity, text), best first; None if unavailable."""
    others = [o for o in others if _key(o)]
    if not others:
        return []
    vs = vectors([text] + others)
    if vs is None:
        return None
    scores = vs[1:] @ vs[0]
    order = np.argsort(-scores)[:k]
    return [(float(scores[i]), others[i]) for i in order]


def duplicate_of(text: str, others: List[str], threshold: Optional[float] = None) -> Optional[Tuple[float, str]]:
    """The closest of `others` if it is close enough to be the same video, else None."""
    best = similar(text, others, k=1)
    if not best:
        return None
    score, match = best[0]
    return (score, match) if score >= (threshold or config.TOPIC_DUP_SIMILARITY) else None


def save(texts: Optional[Iterable[str]] = None) -> int:
    """Write the index (all known vectors, plus `texts` embedded first). Returns its size."""
    if texts is not None and vectors(list(texts)) is None:
        return 0
    _load_file()
    if not _vectors:
        return 0
    keys = sorted(_vectors)
    path = Path(config.TOPIC_INDEX_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, texts=np.array(keys), vectors=np.stack([_vectors[k] for k in keys]).astype(np.float16))
    return len(keys)


def reset() -> None:
    """Forget everything loaded (tests)."""
    global _loaded
    _vectors.clear()
    _loaded = False
