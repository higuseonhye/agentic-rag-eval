from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.memory.models import MemoryEvent, MemoryItem
from app.memory.policies import MemoryPolicy, needs_approval


class MemoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_item(
        self,
        *,
        kind: str,
        content: str,
        title: str | None = None,
        scope: str = "global",
        visibility: str = "internal",
        content_json: dict[str, Any] | None = None,
        confidence: float | None = None,
        provenance_run_id: str | None = None,
        provenance_step_id: str | None = None,
        provenance_doc_ids: list[str] | None = None,
        provenance_chunk_ids: list[str] | None = None,
        created_by: str | None = None,
        policy: MemoryPolicy | None = None,
    ) -> MemoryItem:
        status = "pending" if needs_approval(kind, policy) else "approved"
        item = MemoryItem(
            kind=kind,
            scope=scope,
            visibility=visibility,
            title=title,
            content=content,
            content_json=content_json,
            confidence=confidence,
            status=status,
            provenance_run_id=provenance_run_id,
            provenance_step_id=provenance_step_id,
            provenance_doc_ids=provenance_doc_ids,
            provenance_chunk_ids=provenance_chunk_ids,
            created_by=created_by,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        self.log_event(memory_id=item.memory_id, action="create", actor=created_by, meta={"kind": kind})
        return item

    def log_event(self, *, memory_id: str, action: str, actor: str | None = None, meta: dict[str, Any] | None = None) -> None:
        ev = MemoryEvent(memory_id=memory_id, action=action, actor=actor, meta=meta)
        self.db.add(ev)
        self.db.commit()

    def approve(self, *, memory_id: str, approved_by: str) -> MemoryItem | None:
        item = self.db.get(MemoryItem, memory_id)
        if item is None:
            return None
        item.status = "approved"
        item.approved_by = approved_by
        item.approved_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)
        self.log_event(memory_id=memory_id, action="approve", actor=approved_by)
        return item

    def reject(self, *, memory_id: str, actor: str) -> MemoryItem | None:
        item = self.db.get(MemoryItem, memory_id)
        if item is None:
            return None
        item.status = "rejected"
        item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)
        self.log_event(memory_id=memory_id, action="reject", actor=actor)
        return item

    def search_text(self, *, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = query.strip()
        stmt = text(
            """
            SELECT memory_id, title, kind, scope, status, confidence,
                   ts_rank_cd(to_tsvector('english', content), websearch_to_tsquery('english', :q)) AS rank
            FROM memory_items
            WHERE status = 'approved'
              AND to_tsvector('english', content) @@ websearch_to_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :limit
            """
        )
        rows = self.db.execute(stmt, {"q": q, "limit": limit}).mappings().all()
        return [dict(r) for r in rows]

    def list_recent(self, *, limit: int = 50) -> list[MemoryItem]:
        return list(self.db.scalars(select(MemoryItem).order_by(MemoryItem.created_at.desc()).limit(limit)))

    def get(self, memory_id: str) -> MemoryItem | None:
        return self.db.get(MemoryItem, memory_id)
