from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    eval_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("trace_runs.run_id"), index=True)
    step_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_steps.step_id"), nullable=True, index=True)

    eval_type: Mapped[str] = mapped_column(String(80), index=True)  # retrieval|reasoning|final|process
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

