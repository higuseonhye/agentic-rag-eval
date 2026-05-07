from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkConfig:
    max_chars: int = 1200
    overlap_chars: int = 150


def simple_text_chunk(text: str, cfg: ChunkConfig) -> list[str]:
    """
    Deterministic chunker for MVP (character-based with overlap).
    Replaced later with semantic chunking + metadata-aware splitting.
    """
    t = (text or "").strip()
    if not t:
        return []

    out: list[str] = []
    i = 0
    while i < len(t):
        j = min(len(t), i + cfg.max_chars)
        out.append(t[i:j])
        if j >= len(t):
            break
        i = max(0, j - cfg.overlap_chars)
    return out

