from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.router.adaptive_router import classify_request
from app.workflows.multi_agent_reference import run_multi_agent_incident
from app.workflows.orchestrator import run_adw_workflow


router = APIRouter()


class RunRequest(BaseModel):
    user_request: str = Field(min_length=1)


class RunResponse(BaseModel):
    run_id: str
    task_id: str
    route_level: int
    route_label: str
    route_score: float
    budgets: dict[str, Any]


class MultiAgentRunResponse(BaseModel):
    run_id: str


@router.post("", response_model=RunResponse)
def execute_run(payload: RunRequest, db: Session = Depends(get_db)) -> RunResponse:
    route = classify_request(payload.user_request)
    result = run_adw_workflow(db=db, user_request=payload.user_request, route=route)
    b = route.budgets
    return RunResponse(
        run_id=result["run_id"],
        task_id=result["task_id"],
        route_level=route.level,
        route_label=route.label,
        route_score=route.score,
        budgets={
            "max_retrieval_iterations": b.max_retrieval_iterations,
            "max_workflow_iterations": b.max_workflow_iterations,
            "max_tools": b.max_tools,
            "latency_budget_ms": b.latency_budget_ms,
            "use_graph": b.use_graph,
            "retrieval_mode": b.retrieval_mode,
        },
    )


@router.post("/multi-agent", response_model=MultiAgentRunResponse)
def execute_multi_agent(payload: RunRequest, db: Session = Depends(get_db)) -> MultiAgentRunResponse:
    """Reference LangGraph multi-agent workflow (incident analysis subgraph chain)."""
    out = run_multi_agent_incident(db=db, user_request=payload.user_request)
    return MultiAgentRunResponse(run_id=out["run_id"])
