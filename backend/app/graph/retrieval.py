from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.graph.neo4j_store import get_graph_store
from app.retrieval.types import RetrievalResult


def graph_augment_retrieval(
    *,
    db: Session,
    seed_chunk_ids: list[str],
    limit: int = 6,
) -> tuple[list[RetrievalResult], dict[str, Any]]:
    """
    Expand retrieval with chunks that share entities with seed chunks (1-hop in Neo4j).
    """
    diagnostics: dict[str, Any] = {"graph_augment": True}
    store = get_graph_store()
    if store is None:
        diagnostics["graph_skipped"] = "neo4j_unavailable"
        return [], diagnostics

    extra_ids = store.neighbor_chunk_ids(seed_chunk_ids, limit=limit)
    diagnostics["graph_neighbor_ids"] = extra_ids
    if not extra_ids:
        return [], diagnostics

    stmt = text("SELECT chunk_id, doc_id, text FROM chunks WHERE chunk_id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    rows = db.execute(stmt, {"ids": extra_ids}).mappings().all()
    out: list[RetrievalResult] = []
    for r in rows:
        out.append(
            RetrievalResult(
                chunk_id=str(r["chunk_id"]),
                doc_id=str(r["doc_id"]),
                text=str(r["text"]),
                source="neo4j_graph",
                score=0.35,
                metadata={"via": "entity_overlap"},
            )
        )
    return out, diagnostics
