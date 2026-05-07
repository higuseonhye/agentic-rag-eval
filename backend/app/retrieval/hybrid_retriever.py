from __future__ import annotations

import math
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.chroma_client import get_chroma_client, get_default_collection_name
from app.retrieval.diagnostics import doc_diversity, redundancy_score
from app.retrieval.reranker import lexical_rerank
from app.retrieval.types import RetrievalResult


def _tokenize_for_coverage(q: str) -> set[str]:
    toks = re.findall(r"[a-zA-Z0-9]{3,}", (q or "").lower())
    return set(toks)


def compute_coverage_score(query: str, contexts: list[str]) -> float:
    """
    Simple retrieval coverage heuristic: fraction of query tokens that appear in any retrieved context.
    This is not a substitute for contextual recall, but works as a fast diagnostic signal.
    """
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


def hybrid_retrieve(
    *,
    db: Session,
    query: str,
    k: int = 6,
    alpha: float = 0.6,  # vector weight
) -> tuple[list[RetrievalResult], dict[str, Any]]:
    """
    MVP hybrid retrieval:
    - vector search via Chroma (server)
    - keyword search via Postgres full-text search over `chunks.text`
    - merge by normalized scores
    """
    q = query.strip()
    diagnostics: dict[str, Any] = {"query": q, "k": k, "alpha": alpha}

    # Vector side
    vector_results: list[RetrievalResult] = []
    try:
        client = get_chroma_client()
        col = client.get_or_create_collection(get_default_collection_name())
        res = col.query(query_texts=[q], n_results=k, include=["documents", "metadatas", "distances"])
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        # Convert to similarity-like score (lower dist -> higher score)
        sims = [1.0 / (1.0 + float(d)) for d in dists]
        for doc_text, md, sim in zip(docs, metas, sims, strict=False):
            chunk_id = str(md.get("chunk_id") or md.get("id") or "")
            vector_results.append(
                RetrievalResult(
                    chunk_id=chunk_id or "unknown",
                    doc_id=md.get("doc_id"),
                    text=str(doc_text),
                    source="chroma",
                    score=float(sim),
                    metadata=dict(md),
                )
            )
        diagnostics["vector_count"] = len(vector_results)
    except Exception as e:  # noqa: BLE001
        diagnostics["vector_error"] = str(e)

    # Keyword side (Postgres FTS)
    keyword_results: list[RetrievalResult] = []
    try:
        # websearch_to_tsquery gives a decent user-like query parsing.
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

    # Merge
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

    # Reranker hook (baseline lexical reranker for MVP)
    reranked, rerank_info = lexical_rerank(q, merged[:24])
    diagnostics["rerank"] = rerank_info

    topk = reranked[:k]
    diagnostics["merged_count"] = len(topk)
    diagnostics["coverage_score"] = compute_coverage_score(q, [r.text for r in topk])
    diagnostics["redundancy_score"] = redundancy_score([r.text for r in topk])
    diagnostics["doc_diversity"] = doc_diversity([{"doc_id": r.doc_id} for r in topk])
    return topk, diagnostics

