from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.retrieval.models import Chunk, Document


class RetrievalRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(
        self,
        *,
        title: str | None,
        source: str | None,
        metadata: dict[str, Any] | None,
    ) -> Document:
        doc = Document(title=title, source=source, meta=metadata)
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def add_chunks(
        self,
        *,
        doc_id: str,
        chunk_texts: list[str],
        chunk_metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        for idx, text in enumerate(chunk_texts):
            c = Chunk(doc_id=doc_id, index_in_doc=idx, text=text, meta=chunk_metadata)
            self.db.add(c)
            chunks.append(c)
        self.db.commit()
        for c in chunks:
            self.db.refresh(c)
        return chunks

    def add_chunks_per_meta(
        self,
        *,
        doc_id: str,
        chunk_texts: list[str],
        chunk_metas: list[dict[str, Any] | None] | None = None,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        metas = chunk_metas or [None] * len(chunk_texts)
        if len(metas) != len(chunk_texts):
            raise ValueError("chunk_metas length must match chunk_texts")
        for idx, text in enumerate(chunk_texts):
            c = Chunk(doc_id=doc_id, index_in_doc=idx, text=text, meta=metas[idx])
            self.db.add(c)
            chunks.append(c)
        self.db.commit()
        for c in chunks:
            self.db.refresh(c)
        return chunks

    def list_documents(self, *, limit: int = 50) -> list[Document]:
        return self.db.execute(select(Document).order_by(Document.created_at.desc()).limit(limit)).scalars().all()

