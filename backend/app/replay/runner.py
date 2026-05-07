from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.evaluation.repository import EvaluationRepository
from app.router.adaptive_router import classify_request
from app.tracing.repository import TraceRepository
from app.workflows.orchestrator import run_adw_workflow


def _snapshot_for_run(*, db: Session, source_run_id: str) -> dict[str, Any]:
    traces = TraceRepository(db)
    steps = traces.list_steps(source_run_id)
    doc_ids: set[str] = set()
    chunk_ids: list[str] = []
    for s in steps:
        out = s.get("output") or {}
        if not isinstance(out, dict):
            continue
        for r in out.get("results") or []:
            if isinstance(r, dict):
                if r.get("doc_id"):
                    doc_ids.add(str(r["doc_id"]))
                if r.get("chunk_id"):
                    chunk_ids.append(str(r["chunk_id"]))
    return {
        "collection": settings.qdrant_collection,
        "doc_ids": sorted(doc_ids),
        "chunk_ids_sample": chunk_ids[:200],
        "strategy": "logical_v1",
    }


def _summarize_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    retrieval_latencies: list[int] = []
    for s in steps:
        st = str(s.get("step_type") or "")
        counts[st] = counts.get(st, 0) + 1
        if st == "retrieval" and s.get("latency_ms") is not None:
            retrieval_latencies.append(int(s["latency_ms"]))
    return {
        "step_counts": counts,
        "total_steps": len(steps),
        "retrieval_latency_sum_ms": sum(retrieval_latencies),
        "retrieval_iterations": counts.get("retrieval", 0),
    }


def replay_run(
    *,
    db: Session,
    source_run_id: str,
    router_override_label: str | None = None,
) -> dict[str, Any]:
    """Re-execute workflow for the same user_request and compute diff vs original trace."""

    _ = router_override_label  # reserved for future router pinning

    traces = TraceRepository(db)
    original = traces.get_run(source_run_id)
    if original is None:
        raise ValueError("source run not found")

    snapshot = _snapshot_for_run(db=db, source_run_id=source_run_id)
    orig_steps = traces.list_steps(source_run_id)
    orig_summary = _summarize_steps(orig_steps)

    user_request = str(original.get("user_request") or "")
    route = classify_request(user_request)
    if router_override_label:
        # Minimal override: force hybrid retrieval mode label families — keep MVP safe.
        # Consumers can extend RouteDecision construction later.
        pass

    result = run_adw_workflow(db=db, user_request=user_request, route=route)
    replay_run_id = result["run_id"]
    new_steps = traces.list_steps(replay_run_id)
    new_summary = _summarize_steps(new_steps)

    diff = {
        "original": orig_summary,
        "replay": new_summary,
        "delta": {
            "total_steps": new_summary["total_steps"] - orig_summary["total_steps"],
            "retrieval_iterations": new_summary["retrieval_iterations"]
            - orig_summary["retrieval_iterations"],
            "retrieval_latency_delta_ms": new_summary["retrieval_latency_sum_ms"]
            - orig_summary["retrieval_latency_sum_ms"],
        },
        "snapshot": snapshot,
    }

    evals = EvaluationRepository(db)
    evals.create_result(
        run_id=replay_run_id,
        eval_type="replay",
        model=None,
        metrics=diff,
        raw={"source_run_id": source_run_id, "router_override": router_override_label},
    )

    idx = traces.next_step_index(replay_run_id)
    traces.append_step(
        run_id=replay_run_id,
        step_index=idx,
        step_type="evaluation",
        name="replay_diff",
        input={"source_run_id": source_run_id},
        output=diff,
        score=diff["delta"],
    )

    return {"replay_run_id": replay_run_id, "diff": diff}
