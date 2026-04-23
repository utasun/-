"""埋め込み + 選好ベクトルによる関連度スコアリング。

cold start 期間中 (feedback が足りない) は全件通す。
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable

import numpy as np

from .paper import Paper
from . import state_store

log = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer  # type: ignore
    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> np.ndarray:
    vec = _model().encode(text or "", normalize_embeddings=True)
    return np.asarray(vec, dtype=np.float32)


def _mean(vecs: list[list[float]]) -> np.ndarray | None:
    if not vecs:
        return None
    arr = np.asarray(vecs, dtype=np.float32)
    m = arr.mean(axis=0)
    n = np.linalg.norm(m)
    return m / n if n > 0 else None


def score_papers(
    papers: Iterable[Paper],
    pref: dict,
    keyword_weights: dict[str, float] | None = None,
) -> list[Paper]:
    """papers に `score` を埋めて返す (コピーせず in-place)。"""
    liked = _mean(pref.get("liked_embeddings", []))
    disliked = _mean(pref.get("disliked_embeddings", []))
    weights = keyword_weights or pref.get("keyword_weights", {})

    papers = list(papers)
    for p in papers:
        base = 0.0
        if liked is not None or disliked is not None:
            v = embed(f"{p.title}\n{p.abstract}")
            if liked is not None:
                base += float(np.dot(v, liked))
            if disliked is not None:
                base -= float(np.dot(v, disliked))
        # キーワード重み加算
        bonus = 0.0
        for kw in p.keywords_matched:
            bonus += weights.get(kw, 0.0)
        p.score = base + bonus
    papers.sort(key=lambda x: (x.score or 0.0), reverse=True)
    return papers


def apply_threshold(
    papers: list[Paper],
    threshold: float,
    cold_start_min: int,
    pref: dict,
) -> list[Paper]:
    fc = pref.get("feedback_count", {})
    total = int(fc.get("like", 0)) + int(fc.get("dislike", 0))
    if total < cold_start_min:
        log.info("Cold start (%d < %d) — skipping threshold filter", total, cold_start_min)
        return papers
    kept = [p for p in papers if (p.score or 0.0) >= threshold]
    log.info("Applied threshold %.3f: %d → %d", threshold, len(papers), len(kept))
    return kept
