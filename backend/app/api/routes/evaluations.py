from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.evaluation.repository import EvaluationRepository
from app.tracing.repository import TraceRepository


router = APIRouter()


@router.get("/{run_id}")
def list_evaluations(run_id: str, db: Session = Depends(get_db)) -> dict:
    traces = TraceRepository(db)
    if traces.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    repo = EvaluationRepository(db)
    return {"evaluations": repo.list_results_for_run(run_id=run_id)}

