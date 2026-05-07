from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MemoryItem(Base):
    """Persistent agentic memory with governance + provenance."""

    __tablename__ = "memory_items"

    memory_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    kind: Mapped[str] = mapped_column(String(40), index=True)  # episodic|semantic|preference|constraint|strategy|failure
    scope: Mapped[str] = mapped_column(String(40), default="global", index=True)
    visibility: Mapped[str] = mapped_column(String(40), default="internal")  # internal|org|public

    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|approved|rejected|superseded

    provenance_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provenance_step_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provenance_doc_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    provenance_chunk_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ttl_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_memory_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MemoryEvent(Base):
    """Append-only audit trail for memory mutations."""

    __tablename__ = "memory_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    memory_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_items.memory_id"), index=True)
    action: Mapped[str] = mapped_column(String(40))  # create|update|approve|reject|read
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
