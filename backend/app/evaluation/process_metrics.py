from __future__ import annotations

from typing import Any


def compute_process_metrics(*, steps: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Deterministic process-aware metrics (MVP).
    These are scaffolds that become richer as we add agents/tools/loops.
    """
    tool_calls = sum(1 for s in steps if s.get("step_type") == "tool")
    retrieval_steps = [s for s in steps if s.get("step_type") == "retrieval"]
    total_steps = len(steps)

    coverage_scores = []
    for s in retrieval_steps:
        score = (s.get("score") or {}).get("coverage_score")
        if isinstance(score, (int, float)):
            coverage_scores.append(float(score))

    return {
        "total_steps": total_steps,
        "tool_call_count": tool_calls,
        "retrieval_step_count": len(retrieval_steps),
        "retrieval_coverage_avg": (sum(coverage_scores) / len(coverage_scores)) if coverage_scores else None,
    }

