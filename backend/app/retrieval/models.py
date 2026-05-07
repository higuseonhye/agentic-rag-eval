from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id: Mapped[str] = mapped_column(String(64), ForeignKey("documents.doc_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    index_in_doc: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")

