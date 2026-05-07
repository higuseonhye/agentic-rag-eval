from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.memory.repository import MemoryRepository
from app.tracing.repository import TraceRepository


router = APIRouter()


class MemoryCreateRequest(BaseModel):
    kind: str = Field(min_length=1)
    content: str = Field(min_length=1)
    title: str | None = None
    scope: str = "global"
    visibility: str = "internal"
    content_json: dict[str, Any] | None = None
    confidence: float | None = None
    provenance_run_id: str | None = None
    provenance_step_id: str | None = None
    provenance_doc_ids: list[str] | None = None
    provenance_chunk_ids: list[str] | None = None
    created_by: str | None = None


class MemoryApproveRequest(BaseModel):
    memory_id: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)


class MemoryApproveByPathRequest(BaseModel):
    approved_by: str = Field(min_length=1)


def _trace_memory_write(
    traces: TraceRepository,
    *,
    run_id: str,
    action: str,
    payload: dict[str, Any],
    memory_id: str,
) -> None:
    idx = traces.next_step_index(run_id)
    traces.append_step(
        run_id=run_id,
        step_index=idx,
        step_type="memory",
        name=action,
        input=payload,
        output={"memory_id": memory_id, "status": payload.get("status")},
    )


def _trace_memory_read(
    traces: TraceRepository,
    *,
    run_id: str,
    query: str,
    hits: list[dict[str, Any]],
) -> None:
    idx = traces.next_step_index(run_id)
    traces.append_step(
        run_id=run_id,
        step_index=idx,
        step_type="memory",
        name="search",
        input={"query": query},
        output={"hit_count": len(hits), "top_ids": [h.get("memory_id") for h in hits[:8]]},
    )


@router.post("/items")
def create_memory_item(payload: MemoryCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = MemoryRepository(db)
    item = repo.create_item(
        kind=payload.kind,
        content=payload.content,
        title=payload.title,
        scope=payload.scope,
        visibility=payload.visibility,
        content_json=payload.content_json,
        confidence=payload.confidence,
        provenance_run_id=payload.provenance_run_id,
        provenance_step_id=payload.provenance_step_id,
        provenance_doc_ids=payload.provenance_doc_ids,
        provenance_chunk_ids=payload.provenance_chunk_ids,
        created_by=payload.created_by,
    )
    if payload.provenance_run_id:
        traces = TraceRepository(db)
        if traces.get_run(payload.provenance_run_id):
            _trace_memory_write(
                traces,
                run_id=payload.provenance_run_id,
                action="write",
                payload={
                    "kind": payload.kind,
                    "title": payload.title,
                    "status": item.status,
                    "content_preview": payload.content[:500],
                },
                memory_id=item.memory_id,
            )
    return {"memory_id": item.memory_id, "status": item.status}


def _approve_memory(db: Session, *, memory_id: str, approved_by: str) -> dict[str, Any]:
    repo = MemoryRepository(db)
    item = repo.approve(memory_id=memory_id, approved_by=approved_by)
    if item is None:
        raise HTTPException(status_code=404, detail="memory not found")
    if item.provenance_run_id:
        traces = TraceRepository(db)
        if traces.get_run(item.provenance_run_id):
            _trace_memory_write(
                traces,
                run_id=item.provenance_run_id,
                action="approve",
                payload={"approved_by": approved_by, "status": item.status},
                memory_id=item.memory_id,
            )
    return {"memory_id": item.memory_id, "status": item.status}


@router.post("/approve")
def approve_memory_body(payload: MemoryApproveRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _approve_memory(db, memory_id=payload.memory_id, approved_by=payload.approved_by)


@router.post("/items/{memory_id}/approve")
def approve_memory_path(memory_id: str, payload: MemoryApproveByPathRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _approve_memory(db, memory_id=memory_id, approved_by=payload.approved_by)


@router.get("/search")
def search_memory(
    q: str,
    db: Session = Depends(get_db),
    limit: int = 20,
    trace_run_id: str | None = None,
) -> dict[str, Any]:
    repo = MemoryRepository(db)
    rows = repo.search_text(query=q, limit=limit)
    if trace_run_id:
        traces = TraceRepository(db)
        if traces.get_run(trace_run_id):
            _trace_memory_read(traces, run_id=trace_run_id, query=q, hits=rows)
    return {"results": rows}


@router.get("")
def list_memory(db: Session = Depends(get_db), limit: int = 50) -> dict[str, Any]:
    repo = MemoryRepository(db)
    items = repo.list_recent(limit=limit)
    return {
        "items": [
            {
                "memory_id": m.memory_id,
                "kind": m.kind,
                "title": m.title,
                "status": m.status,
                "provenance_run_id": m.provenance_run_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in items
        ]
    }


@router.get("/items/{memory_id}")
def get_memory_item(memory_id: str, db: Session = Depends(get_db), trace_run_id: str | None = None) -> dict[str, Any]:
    repo = MemoryRepository(db)
    item = repo.get(memory_id)
    if item is None:
        raise HTTPException(status_code=404, detail="memory not found")
    if trace_run_id:
        traces = TraceRepository(db)
        if traces.get_run(trace_run_id):
            _trace_memory_read(traces, run_id=trace_run_id, query=f"id:{memory_id}", hits=[{"memory_id": memory_id}])
    return {
        "memory_id": item.memory_id,
        "kind": item.kind,
        "title": item.title,
        "content": item.content,
        "content_json": item.content_json,
        "scope": item.scope,
        "visibility": item.visibility,
        "confidence": item.confidence,
        "status": item.status,
        "provenance_run_id": item.provenance_run_id,
        "version": item.version,
        "created_at": item.created_at.isoformat(),
    }
