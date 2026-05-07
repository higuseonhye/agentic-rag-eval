from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.models import EvaluationResult


class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_result(
        self,
        *,
        run_id: str,
        eval_type: str,
        step_id: str | None = None,
        model: str | None = None,
        metrics: dict[str, Any] | None = None,
        raw: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> EvaluationResult:
        r = EvaluationResult(
            run_id=run_id,
            step_id=step_id,
            eval_type=eval_type,
            model=model,
            metrics=metrics,
            raw=raw,
            error=error,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return r

    def list_results_for_run(self, *, run_id: str) -> list[dict[str, Any]]:
        results = (
            self.db.execute(
                select(EvaluationResult)
                .where(EvaluationResult.run_id == run_id)
                .order_by(EvaluationResult.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "eval_id": r.eval_id,
                "created_at": r.created_at.isoformat(),
                "run_id": r.run_id,
                "step_id": r.step_id,
                "eval_type": r.eval_type,
                "model": r.model,
                "metrics": r.metrics,
                "raw": r.raw,
                "error": r.error,
            }
            for r in results
        ]

