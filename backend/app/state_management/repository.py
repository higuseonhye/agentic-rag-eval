from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.state_management.models import WorkflowTask


class WorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_task(self, *, user_request: str, route_label: str, run_id: str | None) -> WorkflowTask:
        task = WorkflowTask(
            status="running",
            user_request=user_request,
            route_label=route_label,
            run_id=run_id,
            retrieved_contexts=[],
            reasoning_trace=[],
            tool_outputs={},
            execution_history=[],
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def append_history(self, *, task_id: str, entry: dict[str, Any], current_step: str | None = None) -> None:
        task = self.db.get(WorkflowTask, task_id)
        if task is None:
            return
        history = task.execution_history or []
        history.append({"ts": datetime.utcnow().isoformat(), **entry})
        task.execution_history = history
        if current_step is not None:
            task.current_step = current_step
        task.updated_at = datetime.utcnow()
        self.db.commit()

    def complete_task(self, *, task_id: str, final_decision: dict[str, Any]) -> None:
        task = self.db.get(WorkflowTask, task_id)
        if task is None:
            return
        task.status = "completed"
        task.final_decision = final_decision
        task.updated_at = datetime.utcnow()
        self.db.commit()

