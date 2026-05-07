from __future__ import annotations

import re


def extract_entities_heuristic(text: str, *, max_entities: int = 60) -> list[str]:
    """Lightweight entity candidates for graph linking (replace with NER/LLM later)."""
    # Capitalized phrases (simple proper-noun proxy)
    caps = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
    singles = re.findall(r"\b[A-Z][a-z]{2,}\b", text)
    out: list[str] = []
    seen: set[str] = set()
    for e in caps + singles:
        e = e.strip()
        if len(e) < 2 or e.lower() in seen:
            continue
        seen.add(e.lower())
        out.append(e)
        if len(out) >= max_entities:
            break
    return out
