from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryPolicy:
    """Governance: which kinds require approval before becoming active."""

    require_approval_for: frozenset[str]

    @classmethod
    def default(cls) -> MemoryPolicy:
        return cls(require_approval_for=frozenset({"constraint", "strategy", "semantic"}))


def needs_approval(kind: str, policy: MemoryPolicy | None = None) -> bool:
    p = policy or MemoryPolicy.default()
    return kind in p.require_approval_for
