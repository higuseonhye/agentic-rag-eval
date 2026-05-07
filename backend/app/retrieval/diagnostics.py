from __future__ import annotations

import re
from typing import Any


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]{3,}", (s or "").lower()))


def redundancy_score(texts: list[str]) -> float | None:
    """
    Average pairwise Jaccard similarity across retrieved contexts.
    Higher => more redundant retrieval.
    """
    if len(texts) < 2:
        return None
    toks = [_tokens(t) for t in texts]
    pairs = 0
    total = 0.0
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            a, b = toks[i], toks[j]
            if not a and not b:
                continue
            pairs += 1
            total += len(a & b) / max(1, len(a | b))
    if pairs == 0:
        return None
    return total / pairs


def doc_diversity(results: list[dict[str, Any]]) -> dict[str, Any]:
    doc_ids = [r.get("doc_id") for r in results if r.get("doc_id")]
    unique = sorted(set(doc_ids))
    return {"unique_doc_count": len(unique), "doc_ids": unique[:20]}

