from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.tracing.models import AgentStep, TraceRun


class TraceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, *, workflow_name: str, user_request: str, route_label: str) -> TraceRun:
        run = TraceRun(workflow_name=workflow_name, user_request=user_request, route_label=route_label)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def append_step(
        self,
        *,
        run_id: str,
        step_index: int,
        step_type: str,
        name: str | None = None,
        parent_step_id: str | None = None,
        input: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        latency_ms: int | None = None,
        token_usage: dict[str, Any] | None = None,
        score: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AgentStep:
        step = AgentStep(
            run_id=run_id,
            step_index=step_index,
            step_type=step_type,
            name=name,
            parent_step_id=parent_step_id,
            input=input,
            output=output,
            latency_ms=latency_ms,
            token_usage=token_usage,
            score=score,
            error=error,
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def list_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        runs = self.db.execute(select(TraceRun).order_by(TraceRun.created_at.desc()).limit(limit)).scalars().all()
        return [
            {
                "run_id": r.run_id,
                "created_at": r.created_at.isoformat(),
                "workflow_name": r.workflow_name,
                "route_label": r.route_label,
                "user_request": r.user_request,
            }
            for r in runs
        ]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.db.get(TraceRun, run_id)
        if run is None:
            return None
        return {
            "run_id": run.run_id,
            "created_at": run.created_at.isoformat(),
            "workflow_name": run.workflow_name,
            "route_label": run.route_label,
            "user_request": run.user_request,
            "latency_ms": run.latency_ms,
            "token_usage": run.token_usage,
            "cost_usd": run.cost_usd,
        }

    def next_step_index(self, run_id: str) -> int:
        val = self.db.execute(select(func.max(AgentStep.step_index)).where(AgentStep.run_id == run_id)).scalar()
        return int(val if val is not None else -1) + 1

    def list_steps(self, run_id: str) -> list[dict[str, Any]]:
        steps = (
            self.db.execute(
                select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index.asc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "step_id": s.step_id,
                "parent_step_id": s.parent_step_id,
                "run_id": s.run_id,
                "step_index": s.step_index,
                "step_type": s.step_type,
                "name": s.name,
                "input": s.input,
                "output": s.output,
                "latency_ms": s.latency_ms,
                "token_usage": s.token_usage,
                "score": s.score,
                "error": s.error,
                "created_at": s.created_at.isoformat(),
            }
            for s in steps
        ]

