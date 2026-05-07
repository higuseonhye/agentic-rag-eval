from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge_engine.compilation.models import KnowledgeUnit


class KnowledgeUnitRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, unit: KnowledgeUnit) -> KnowledgeUnit:
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def get(self, unit_id: str) -> KnowledgeUnit | None:
        return self.db.get(KnowledgeUnit, unit_id)

    def list_recent(self, *, limit: int = 50) -> list[KnowledgeUnit]:
        return list(
            self.db.scalars(select(KnowledgeUnit).order_by(KnowledgeUnit.created_at.desc()).limit(limit))
        )

    def to_dict(self, u: KnowledgeUnit) -> dict[str, Any]:
        return {
            "unit_id": u.unit_id,
            "title": u.title,
            "unit_type": u.unit_type,
            "version": u.version,
            "content_text": u.content_text,
            "content_json": u.content_json,
            "citations_chunk_ids": u.citations_chunk_ids,
            "citations_doc_ids": u.citations_doc_ids,
            "constraints": u.constraints,
            "applicability": u.applicability,
            "confidence": u.confidence,
            "provenance_run_id": u.provenance_run_id,
            "supersedes_unit_id": u.supersedes_unit_id,
            "created_at": u.created_at.isoformat(),
        }
