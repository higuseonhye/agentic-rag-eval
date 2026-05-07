from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    doc_id: str | None
    text: str
    source: str
    score: float
    metadata: dict[str, Any]

