from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TraceRun(Base):
    __tablename__ = "trace_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # High-level grouping
    workflow_name: Mapped[str] = mapped_column(String(200), default="adw_orchestrator")
    user_request: Mapped[str] = mapped_column(Text)
    route_label: Mapped[str] = mapped_column(String(50), default="unknown")  # simple | complex

    # Aggregate stats (optional)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentStep.step_index.asc()",
    )


class AgentStep(Base):
    """
    OpenTelemetry-like step event for workflow tracing.
    Matches the product schema:
      step_id, parent_step_id, step_type, input/output, latency_ms, token_usage, score
    """

    __tablename__ = "agent_steps"

    step_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("trace_runs.run_id"), index=True)
    parent_step_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    step_index: Mapped[int] = mapped_column(Integer, index=True)
    step_type: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    input: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    score: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    run: Mapped["TraceRun"] = relationship(back_populates="steps")

