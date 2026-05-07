from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Artifact(Base):
    """Multimodal artifact root record (video-lite v1)."""

    __tablename__ = "artifacts"

    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    kind: Mapped[str] = mapped_column(String(40), index=True)  # video
    storage_path: Mapped[str] = mapped_column(String(2000))
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    transcript_doc_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("documents.doc_id"), nullable=True)
