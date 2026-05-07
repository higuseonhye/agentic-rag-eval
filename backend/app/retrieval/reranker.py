from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.retrieval.types import RetrievalResult


@dataclass(frozen=True)
class RerankConfig:
    enabled: bool = True
    max_candidates: int = 24


def _query_tokens(q: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]{3,}", (q or "").lower()))


def lexical_rerank(query: str, results: list[RetrievalResult]) -> tuple[list[RetrievalResult], dict]:
    """
    Baseline reranker hook (deterministic, lightweight, Python-only).
    Scores by token overlap between query and chunk text.

    This is intentionally a *hook* so we can swap in bge-reranker / ColBERT later
    without changing tracing or the workflow contract.
    """
    qt = _query_tokens(query)
    if not qt or not results:
        return results, {"reranker": "lexical", "applied": False}

    rescored: list[tuple[float, RetrievalResult]] = []
    for r in results:
        text = (r.text or "").lower()
        hit = sum(1 for t in qt if t in text)
        overlap = hit / max(1, len(qt))
        rescored.append((r.score + 0.25 * overlap, r))

    rescored.sort(key=lambda x: x[0], reverse=True)
    out = [
        RetrievalResult(
            chunk_id=r.chunk_id,
            doc_id=r.doc_id,
            text=r.text,
            source="reranked",
            score=float(s),
            metadata={**r.metadata, "lexical_overlap": float(s - r.score)},
        )
        for s, r in rescored
    ]
    return out, {"reranker": "lexical", "applied": True}

