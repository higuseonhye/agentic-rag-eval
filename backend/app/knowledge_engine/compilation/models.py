from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class KnowledgeUnit(Base):
    """Compiled operational knowledge artifact."""

    __tablename__ = "knowledge_units"

    unit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    title: Mapped[str] = mapped_column(String(500))
    unit_type: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    content_text: Mapped[str] = mapped_column(Text)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    citations_chunk_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    citations_doc_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    constraints: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    applicability: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    provenance_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    supersedes_unit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_units.unit_id"), nullable=True)
