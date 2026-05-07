from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.tracing.repository import TraceRepository


router = APIRouter()


@router.get("/{run_id}")
def get_trace(run_id: str, db: Session = Depends(get_db)) -> dict:
    repo = TraceRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    steps = repo.list_steps(run_id)
    return {
        "run": run,
        "steps": steps,
    }


@router.get("")
def list_traces(db: Session = Depends(get_db), limit: int = 50) -> dict:
    repo = TraceRepository(db)
    return {"runs": repo.list_runs(limit=limit)}

