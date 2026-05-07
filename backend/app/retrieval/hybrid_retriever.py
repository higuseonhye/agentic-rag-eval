from __future__ import annotations

import math
import re
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.diagnostics import doc_diversity, redundancy_score
from app.retrieval.reranker import lexical_rerank
from app.retrieval.types import RetrievalResult
from app.retrieval.vector_store import get_vector_store

RetrievalMode = Literal["hybrid", "dense_only", "sparse_only"]


def _tokenize_for_coverage(q: str) -> set[str]:
    toks = re.findall(r"[a-zA-Z0-9]{3,}", (q or "").lower())
    return set(toks)


def compute_coverage_score(query: str, contexts: list[str]) -> float:
    qt = _tokenize_for_coverage(query)
    if not qt:
        return 0.0
    joined = " ".join(contexts).lower()
    hit = sum(1 for t in qt if t in joined)
    return hit / max(1, len(qt))


def _minmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if math.isclose(lo, hi):
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def _sparse_search(db: Session, q: str, k: int) -> tuple[list[RetrievalResult], dict[str, Any]]:
    diagnostics: dict[str, Any] = {}
    keyword_results: list[RetrievalResult] = []
    try:
        stmt = text(
            """
            SELECT chunk_id, doc_id, text,
                   ts_rank_cd(to_tsvector('english', text), websearch_to_tsquery('english', :q)) AS rank
            FROM chunks
            WHERE to_tsvector('english', text) @@ websearch_to_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :k
            """
        )
        rows = db.execute(stmt, {"q": q, "k": k}).mappings().all()
        for r in rows:
            keyword_results.append(
                RetrievalResult(
                    chunk_id=str(r["chunk_id"]),
                    doc_id=str(r["doc_id"]),
                    text=str(r["text"]),
                    source="postgres_fts",
                    score=float(r["rank"] or 0.0),
                    metadata={"rank": float(r["rank"] or 0.0)},
                )
            )
        diagnostics["keyword_count"] = len(keyword_results)
    except Exception as e:  # noqa: BLE001
        diagnostics["keyword_error"] = str(e)
    return keyword_results, diagnostics


def _dense_search(q: str, k: int) -> tuple[list[RetrievalResult], dict[str, Any]]:
    store = get_vector_store()
    return store.query_similar(query=q, k=k)


def hybrid_retrieve(
    *,
    db: Session,
    query: str,
    k: int = 6,
    alpha: float = 0.6,
    mode: RetrievalMode = "hybrid",
) -> tuple[list[RetrievalResult], dict[str, Any]]:
    """
    Hybrid retrieval:
    - dense: VectorStore (Qdrant or Chroma per settings)
    - sparse: Postgres FTS
    - fusion + lexical rerank
    """
    q = query.strip()
    diagnostics: dict[str, Any] = {"query": q, "k": k, "alpha": alpha, "mode": mode}

    vector_results: list[RetrievalResult] = []
    if mode in ("hybrid", "dense_only"):
        try:
            vector_results, vdiag = _dense_search(q, k)
            diagnostics["dense_backend"] = vdiag.get("backend")
            diagnostics["vector_count"] = vdiag.get("vector_count", len(vector_results))
            if "vector_error" in vdiag:
                diagnostics["vector_error"] = vdiag["vector_error"]
            if vdiag.get("collection"):
                diagnostics["vector_collection"] = vdiag["collection"]
        except Exception as e:  # noqa: BLE001
            diagnostics["vector_error"] = str(e)

    keyword_results: list[RetrievalResult] = []
    k_sparse_diag: dict[str, Any] = {}
    if mode in ("hybrid", "sparse_only"):
        keyword_results, k_sparse_diag = _sparse_search(db, q, k)
        diagnostics.update(k_sparse_diag)

    if mode == "dense_only":
        merged = sorted(vector_results, key=lambda r: r.score, reverse=True)[: max(k, 1)]
        diagnostics["merged_count_pre_rerank"] = len(merged)
        diagnostics["pre_rerank_top_ids"] = [r.chunk_id for r in merged[:k]]
        reranked, rerank_info = lexical_rerank(q, merged[:24])
        diagnostics["rerank"] = rerank_info
        topk = reranked[:k]
        diagnostics["merged_count"] = len(topk)
        diagnostics["coverage_score"] = compute_coverage_score(q, [r.text for r in topk])
        diagnostics["redundancy_score"] = redundancy_score([r.text for r in topk])
        diagnostics["doc_diversity"] = doc_diversity([{"doc_id": r.doc_id} for r in topk])
        return topk, diagnostics

    if mode == "sparse_only":
        merged = sorted(keyword_results, key=lambda r: r.score, reverse=True)[: max(k, 1)]
        diagnostics["merged_count_pre_rerank"] = len(merged)
        diagnostics["pre_rerank_top_ids"] = [r.chunk_id for r in merged[:k]]
        reranked, rerank_info = lexical_rerank(q, merged[:24])
        diagnostics["rerank"] = rerank_info
        topk = reranked[:k]
        diagnostics["merged_count"] = len(topk)
        diagnostics["coverage_score"] = compute_coverage_score(q, [r.text for r in topk])
        diagnostics["redundancy_score"] = redundancy_score([r.text for r in topk])
        diagnostics["doc_diversity"] = doc_diversity([{"doc_id": r.doc_id} for r in topk])
        return topk, diagnostics

    # hybrid merge
    by_id: dict[str, RetrievalResult] = {}
    vec_norm = _minmax([r.score for r in vector_results])
    key_norm = _minmax([r.score for r in keyword_results])

    for r, s in zip(vector_results, vec_norm, strict=False):
        by_id[r.chunk_id] = RetrievalResult(
            chunk_id=r.chunk_id,
            doc_id=r.doc_id,
            text=r.text,
            source=r.source,
            score=alpha * float(s),
            metadata=r.metadata,
        )
    for r, s in zip(keyword_results, key_norm, strict=False):
        if r.chunk_id in by_id:
            prior = by_id[r.chunk_id]
            by_id[r.chunk_id] = RetrievalResult(
                chunk_id=prior.chunk_id,
                doc_id=prior.doc_id or r.doc_id,
                text=prior.text or r.text,
                source="hybrid",
                score=prior.score + (1.0 - alpha) * float(s),
                metadata={**prior.metadata, **r.metadata},
            )
        else:
            by_id[r.chunk_id] = RetrievalResult(
                chunk_id=r.chunk_id,
                doc_id=r.doc_id,
                text=r.text,
                source=r.source,
                score=(1.0 - alpha) * float(s),
                metadata=r.metadata,
            )

    merged = sorted(by_id.values(), key=lambda r: r.score, reverse=True)[: max(k, 1)]
    diagnostics["merged_count_pre_rerank"] = len(merged)
    diagnostics["pre_rerank_top_ids"] = [r.chunk_id for r in merged[:k]]

    reranked, rerank_info = lexical_rerank(q, merged[:24])
    diagnostics["rerank"] = rerank_info

    topk = reranked[:k]
    diagnostics["merged_count"] = len(topk)
    diagnostics["coverage_score"] = compute_coverage_score(q, [r.text for r in topk])
    diagnostics["redundancy_score"] = redundancy_score([r.text for r in topk])
    diagnostics["doc_diversity"] = doc_diversity([{"doc_id": r.doc_id} for r in topk])
    return topk, diagnostics
