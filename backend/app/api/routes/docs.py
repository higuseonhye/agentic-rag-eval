from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.retrieval.chroma_client import get_chroma_client, get_default_collection_name
from app.retrieval.chunking import ChunkConfig, simple_text_chunk
from app.retrieval.repository import RetrievalRepository


router = APIRouter()


class IngestRequest(BaseModel):
    title: str | None = None
    source: str | None = None
    metadata: dict[str, Any] | None = None
    text: str = Field(min_length=1)


class IngestResponse(BaseModel):
    doc_id: str
    chunk_count: int


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    repo = RetrievalRepository(db)
    doc = repo.create_document(title=payload.title, source=payload.source, metadata=payload.metadata)

    cfg = ChunkConfig()
    chunks = simple_text_chunk(payload.text, cfg)
    stored = repo.add_chunks(doc_id=doc.doc_id, chunk_texts=chunks, chunk_metadata=payload.metadata)

    # Index into Chroma (vector index). For now we rely on Chroma's default embedding fn
    # (good enough for scaffolding; next step adds explicit embedding model control).
    client = get_chroma_client()
    col = client.get_or_create_collection(get_default_collection_name())
    col.add(
        ids=[c.chunk_id for c in stored],
        documents=[c.text for c in stored],
        metadatas=[
            {"doc_id": c.doc_id, "chunk_id": c.chunk_id, "index_in_doc": c.index_in_doc, **(c.meta or {})}
            for c in stored
        ],
    )

    return IngestResponse(doc_id=doc.doc_id, chunk_count=len(stored))

