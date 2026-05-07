from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.graph.neo4j_store import get_graph_store
from app.knowledge_engine.compilation.models import KnowledgeUnit
from app.knowledge_engine.compilation.repository import KnowledgeUnitRepository
from app.retrieval.hybrid_retriever import hybrid_retrieve
from app.retrieval.models import Chunk
from app.retrieval.vector_store import get_vector_store


def _chunks_by_ids(db: Session, chunk_ids: list[str]) -> list[Chunk]:
    if not chunk_ids:
        return []
    rows = db.execute(select(Chunk).where(Chunk.chunk_id.in_(chunk_ids))).scalars().all()
    return list(rows)


def compile_knowledge_unit(
    *,
    db: Session,
    title: str,
    unit_type: str,
    query: str | None,
    chunk_ids: list[str] | None,
    provenance_run_id: str | None,
    confidence: float | None,
    supersedes_unit_id: str | None,
) -> KnowledgeUnit:
    """Build a KnowledgeUnit from retrieved evidence and index it for hybrid retrieval."""

    evidence_texts: list[str] = []
    cite_chunks: list[str] = []
    cite_docs: list[str] = []

    if chunk_ids:
        chunks = _chunks_by_ids(db, chunk_ids)
        for c in chunks:
            evidence_texts.append(c.text)
            cite_chunks.append(c.chunk_id)
            cite_docs.append(c.doc_id)
    elif query:
        results, _diag = hybrid_retrieve(db=db, query=query, k=8, alpha=0.55, mode="hybrid")
        for r in results:
            evidence_texts.append(r.text)
            cite_chunks.append(r.chunk_id)
            if r.doc_id:
                cite_docs.append(r.doc_id)
    else:
        raise ValueError("compile requires either chunk_ids or query")

    body = "\n\n".join(evidence_texts[:24])
    content_json: dict[str, Any] = {
        "evidence_count": len(evidence_texts),
        "compile_mode": "chunk_ids" if chunk_ids else "query_retrieval",
    }

    unit = KnowledgeUnit(
        title=title,
        unit_type=unit_type,
        content_text=body[:120_000],
        content_json=content_json,
        citations_chunk_ids=list(dict.fromkeys(cite_chunks)),
        citations_doc_ids=list(dict.fromkeys(cite_docs)),
        confidence=confidence or 0.65,
        provenance_run_id=provenance_run_id,
        supersedes_unit_id=supersedes_unit_id,
    )

    repo = KnowledgeUnitRepository(db)
    repo.create(unit=unit)

    # Dense index (same vector collection with discriminating metadata)
    store = get_vector_store()
    meta = {
        "kind": "knowledge_unit",
        "unit_id": unit.unit_id,
        "unit_type": unit.unit_type,
        "title": unit.title,
        "doc_id": None,
    }
    store.upsert_chunks(
        ids=[f"ku:{unit.unit_id}"],
        texts=[unit.content_text[:8000]],
        metadatas=[meta],
    )

    graph_store = get_graph_store()
    if graph_store and unit.citations_chunk_ids:
        for cid in unit.citations_chunk_ids[:40]:
            graph_store.link_unit_to_chunk(unit_id=unit.unit_id, chunk_id=str(cid))

    return unit
