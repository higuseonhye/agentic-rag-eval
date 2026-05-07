from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.router.adaptive_router import classify_request
from app.workflows.orchestrator import run_adw_workflow


router = APIRouter()


class RunRequest(BaseModel):
    user_request: str = Field(min_length=1)


class RunResponse(BaseModel):
    run_id: str
    task_id: str
    route_label: str
    route_score: float


@router.post("", response_model=RunResponse)
def execute_run(payload: RunRequest, db: Session = Depends(get_db)) -> RunResponse:
    route = classify_request(payload.user_request)
    result = run_adw_workflow(db=db, user_request=payload.user_request, route=route)
    return RunResponse(
        run_id=result["run_id"],
        task_id=result["task_id"],
        route_label=route.label,
        route_score=route.score,
    )

