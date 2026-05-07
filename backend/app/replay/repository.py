from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.replay.models import ReplayJob


class ReplayRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, *, source_run_id: str, snapshot: dict[str, Any] | None) -> ReplayJob:
        job = ReplayJob(source_run_id=source_run_id, snapshot=snapshot, status="pending")
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def complete(self, *, replay_id: str, replay_run_id: str, diff: dict[str, Any]) -> ReplayJob | None:
        job = self.db.get(ReplayJob, replay_id)
        if job is None:
            return None
        job.status = "completed"
        job.replay_run_id = replay_run_id
        job.diff = diff
        self.db.commit()
        self.db.refresh(job)
        return job

    def fail(self, *, replay_id: str, error: str) -> ReplayJob | None:
        job = self.db.get(ReplayJob, replay_id)
        if job is None:
            return None
        job.status = "failed"
        job.error = error[:2000]
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, replay_id: str) -> ReplayJob | None:
        return self.db.get(ReplayJob, replay_id)
