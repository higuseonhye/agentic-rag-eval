from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.knowledge_engine.pipeline import ingest_document


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
    outcome = ingest_document(
        db=db,
        title=payload.title,
        source=payload.source,
        text=payload.text,
        metadata=payload.metadata,
    )
    return IngestResponse(doc_id=outcome.doc_id, chunk_count=outcome.chunk_count)
