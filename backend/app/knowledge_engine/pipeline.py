from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.graph.neo4j_store import get_graph_store
from app.knowledge_engine.entities import extract_entities_heuristic
from app.retrieval.chunking import ChunkConfig, simple_text_chunk
from app.retrieval.repository import RetrievalRepository
from app.retrieval.vector_store import get_vector_store


@dataclass
class IngestOutcome:
    doc_id: str
    chunk_count: int
    entities_per_chunk: list[tuple[str, list[str]]]


def ingest_document(
    *,
    db: Session,
    title: str | None,
    source: str | None,
    text: str,
    metadata: dict[str, Any] | None,
) -> IngestOutcome:
    """
    Knowledge Engine ingestion pipeline:
    chunk → sparse (Postgres rows) → dense (VectorStore) → optional graph (Neo4j entities).
    """
    repo = RetrievalRepository(db)
    doc = repo.create_document(title=title, source=source, metadata=metadata)

    cfg = ChunkConfig()
    chunk_texts = simple_text_chunk(text, cfg)
    stored = repo.add_chunks(doc_id=doc.doc_id, chunk_texts=chunk_texts, chunk_metadata=metadata)

    metas = [
        {"doc_id": c.doc_id, "chunk_id": c.chunk_id, "index_in_doc": c.index_in_doc, **(c.meta or {})}
        for c in stored
    ]
    store = get_vector_store()
    store.upsert_chunks(
        ids=[c.chunk_id for c in stored],
        texts=[c.text for c in stored],
        metadatas=metas,
    )

    graph = get_graph_store()
    entities_per_chunk: list[tuple[str, list[str]]] = []
    if graph is not None:
        for c in stored:
            ents = extract_entities_heuristic(c.text)
            entities_per_chunk.append((c.chunk_id, ents))
            graph.sync_chunk_entities(chunk_id=c.chunk_id, doc_id=c.doc_id, entities=ents)

    return IngestOutcome(
        doc_id=doc.doc_id,
        chunk_count=len(stored),
        entities_per_chunk=entities_per_chunk,
    )
