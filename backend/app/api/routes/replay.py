from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.replay.repository import ReplayRepository
from app.replay.runner import _snapshot_for_run, replay_run
from app.tracing.repository import TraceRepository


router = APIRouter()


class ReplayRequest(BaseModel):
    router_override_label: str | None = None


@router.post("/from-run/{run_id}")
def start_replay(run_id: str, payload: ReplayRequest | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    traces = TraceRepository(db)
    if traces.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")

    p = payload or ReplayRequest()
    repo = ReplayRepository(db)
    snap = _snapshot_for_run(db=db, source_run_id=run_id)
    job = repo.create_job(source_run_id=run_id, snapshot=snap)

    try:
        out = replay_run(db=db, source_run_id=run_id, router_override_label=p.router_override_label)
    except ValueError as e:
        repo.fail(replay_id=job.replay_id, error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e

    repo.complete(replay_id=job.replay_id, replay_run_id=out["replay_run_id"], diff=out["diff"])
    return {"replay_id": job.replay_id, "replay_run_id": out["replay_run_id"], "diff": out["diff"]}


@router.get("/jobs/{replay_id}")
def get_replay(replay_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = ReplayRepository(db)
    job = repo.get(replay_id)
    if job is None:
        raise HTTPException(status_code=404, detail="replay not found")
    return {
        "replay_id": job.replay_id,
        "created_at": job.created_at.isoformat(),
        "source_run_id": job.source_run_id,
        "replay_run_id": job.replay_run_id,
        "status": job.status,
        "snapshot": job.snapshot,
        "diff": job.diff,
        "error": job.error,
    }
