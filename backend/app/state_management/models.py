from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    status: Mapped[str] = mapped_column(String(30), default="created")  # created|running|paused|completed|failed
    current_step: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user_request: Mapped[str] = mapped_column(Text)
    route_label: Mapped[str] = mapped_column(String(50), default="unknown")

    # The "WorkflowState" payloads
    retrieved_contexts: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    reasoning_trace: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    tool_outputs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution_history: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)

    final_decision: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("trace_runs.run_id"), nullable=True)
    # relationship is optional; avoid circular import issues at runtime
    trace_run = relationship("TraceRun", primaryjoin="WorkflowTask.run_id==TraceRun.run_id", viewonly=True)

