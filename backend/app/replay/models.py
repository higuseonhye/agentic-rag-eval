from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ReplayJob(Base):
    __tablename__ = "replay_jobs"

    replay_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    source_run_id: Mapped[str] = mapped_column(String(36), index=True)
    replay_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(40), default="pending")  # pending|completed|failed
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
