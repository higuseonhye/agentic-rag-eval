from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.knowledge_engine.compilation.pipeline import compile_knowledge_unit
from app.knowledge_engine.compilation.repository import KnowledgeUnitRepository


router = APIRouter()


class CompileRequest(BaseModel):
    title: str = Field(min_length=1)
    unit_type: str = Field(min_length=1)
    query: str | None = None
    chunk_ids: list[str] | None = None
    provenance_run_id: str | None = None
    confidence: float | None = None
    supersedes_unit_id: str | None = None


@router.post("/compile")
def compile_unit(payload: CompileRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        unit = compile_knowledge_unit(
            db=db,
            title=payload.title,
            unit_type=payload.unit_type,
            query=payload.query,
            chunk_ids=payload.chunk_ids,
            provenance_run_id=payload.provenance_run_id,
            confidence=payload.confidence,
            supersedes_unit_id=payload.supersedes_unit_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    repo = KnowledgeUnitRepository(db)
    return {"unit": repo.to_dict(unit)}


@router.get("/units")
def list_units(db: Session = Depends(get_db), limit: int = 50) -> dict[str, Any]:
    repo = KnowledgeUnitRepository(db)
    units = repo.list_recent(limit=limit)
    return {"units": [repo.to_dict(u) for u in units]}


@router.get("/units/{unit_id}")
def get_unit(unit_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = KnowledgeUnitRepository(db)
    u = repo.get(unit_id)
    if u is None:
        raise HTTPException(status_code=404, detail="unit not found")
    return {"unit": repo.to_dict(u)}
