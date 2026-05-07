from __future__ import annotations

import time
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.core.config import settings
from app.evaluation.hook import run_evaluations_for_run
from app.evaluation.repository import EvaluationRepository
from app.graph.retrieval import graph_augment_retrieval
from app.retrieval.hybrid_retriever import RetrievalResult, hybrid_retrieve
from app.router.adaptive_router import RouteDecision
from app.state_management.repository import WorkflowRepository
from app.tracing.repository import TraceRepository

RetrievalMode = Literal["hybrid", "dense_only", "sparse_only"]


def _rewrite_query_heuristic(original: str, iteration: int) -> str:
    base = original.strip()
    if iteration <= 0:
        return base
    if iteration == 1:
        return f"{base} key details evidence"
    return f"{base} constraints edge cases citations"


class ADWState(TypedDict, total=False):
    user_request: str
    route_level: int
    route_label: str
    route_score: float
    route_reasons: list[str]

    plan: dict[str, Any]
    retrieved_contexts: list[dict[str, Any]]
    reasoning_trace: list[dict[str, Any]]
    report: dict[str, Any]


def _retrieval_mode_from_budget(mode: str) -> RetrievalMode:
    if mode == "dense_only":
        return "dense_only"
    if mode == "sparse_only":
        return "sparse_only"
    return "hybrid"


def _results_to_contexts(results: list[RetrievalResult]) -> list[dict[str, Any]]:
    return [
        {
            "source": r.source,
            "doc_id": r.doc_id,
            "chunk_id": r.chunk_id,
            "text": r.text,
            "metadata": r.metadata,
            "score": r.score,
        }
        for r in results
    ]


def _dedupe_by_chunk(
    primary: list[RetrievalResult],
    extra: list[RetrievalResult],
) -> list[RetrievalResult]:
    seen = {r.chunk_id for r in primary}
    out = list(primary)
    for r in extra:
        if r.chunk_id in seen:
            continue
        seen.add(r.chunk_id)
        out.append(r)
    return out


def _node_plan(state: ADWState) -> ADWState:
    req = state["user_request"]
    state["plan"] = {
        "objective": "produce actionable output grounded in retrieved evidence",
        "steps": [
            {"name": "decompose", "description": "derive sub-questions if needed"},
            {"name": "retrieve", "description": "adaptive hybrid / dense / graph"},
            {"name": "synthesize", "description": "compose report with citations"},
        ],
        "notes": {"input_length": len(req), "route": state.get("route_label")},
    }
    return state


def _node_retrieve(state: ADWState) -> ADWState:
    state["retrieved_contexts"] = state.get("retrieved_contexts", [])
    return state


def _node_reason(state: ADWState) -> ADWState:
    trace = state.get("reasoning_trace", [])
    level = int(state.get("route_level") or 0)
    if level >= 3:
        trace.append(
            {
                "type": "reflection",
                "content": "L3/L4: reflection hook — verify grounding vs retrieved contexts (stub).",
            }
        )
    else:
        trace.append(
            {
                "type": "reflection",
                "content": "MVP: lightweight reasoning trace; expand for critic/verifier agents.",
            }
        )
    state["reasoning_trace"] = trace
    return state


def _node_report(state: ADWState) -> ADWState:
    state["report"] = {
        "kind": "adw_report",
        "summary": "ADW orchestration run completed. See citations and route for strategy used.",
        "route": {
            "level": state.get("route_level"),
            "label": state.get("route_label"),
            "score": state.get("route_score"),
            "reasons": state.get("route_reasons"),
        },
        "citations": [
            {"doc_id": c.get("doc_id"), "chunk_id": c.get("chunk_id"), "source": c.get("source")}
            for c in state.get("retrieved_contexts", [])
        ],
    }
    return state


def _build_graph() -> StateGraph:
    g = StateGraph(ADWState)
    g.add_node("plan", _node_plan)
    g.add_node("retrieve", _node_retrieve)
    g.add_node("reason", _node_reason)
    g.add_node("report", _node_report)

    g.set_entry_point("plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "reason")
    g.add_edge("reason", "report")
    g.add_edge("report", END)
    return g


_GRAPH = _build_graph().compile()


def run_adw_workflow(*, db: Session, user_request: str, route: RouteDecision) -> dict[str, str]:
    traces = TraceRepository(db)
    workflows = WorkflowRepository(db)
    evals = EvaluationRepository(db)

    run = traces.create_run(
        workflow_name="adw_orchestrator",
        user_request=user_request,
        route_label=route.label,
    )
    task = workflows.create_task(
        user_request=user_request,
        route_label=route.label,
        run_id=run.run_id,
    )

    state: ADWState = {
        "user_request": user_request,
        "route_level": route.level,
        "route_label": route.label,
        "route_score": route.score,
        "route_reasons": route.reasons,
        "retrieved_contexts": [],
        "reasoning_trace": [],
    }

    seq = 0
    start = time.perf_counter()
    retrieval_timeline: list[dict[str, Any]] = []
    root_retrieval_step_id: str | None = None
    coverage_prev = 0.0

    b = route.budgets
    rmode = _retrieval_mode_from_budget(b.retrieval_mode)
    max_iter = b.max_retrieval_iterations
    if route.level == 0:
        max_iter = 0
    # L1/L2 may use a single pass unless config overrides
    if route.level in (1, 2) and max_iter < 1:
        max_iter = 1
    max_iter = min(max_iter, settings.max_retrieval_iterations)

    if max_iter == 0:
        state["retrieved_contexts"] = []
        seq += 1
        traces.append_step(
            run_id=run.run_id,
            step_index=seq,
            step_type="router",
            name="no_retrieval",
            input={"route": route.label, "level": route.level},
            output={"reason": "L0 or zero budget — skipped retrieval."},
        )
    else:
        for i in range(max_iter):
            q_i = _rewrite_query_heuristic(user_request, i) if route.level >= 3 else user_request.strip()
            t0 = time.perf_counter()
            results, diagnostics = hybrid_retrieve(
                db=db,
                query=q_i,
                k=6,
                alpha=0.6,
                mode=rmode,
            )
            pre_rerank_ids = list(diagnostics.get("pre_rerank_top_ids") or [])
            result_scores = {r.chunk_id: r.score for r in results}

            if b.use_graph and route.level >= 3 and results:
                g_results, gdiag = graph_augment_retrieval(
                    db=db,
                    seed_chunk_ids=[r.chunk_id for r in results],
                    limit=6,
                )
                results = _dedupe_by_chunk(results, g_results)
                diagnostics = {
                    **diagnostics,
                    "graph": gdiag,
                    "graph_neighbor_ids": gdiag.get("graph_neighbor_ids"),
                    "graph_skipped": gdiag.get("graph_skipped"),
                }
            # Rerank delta: record order before/after second lexical pass is already in hybrid;
            # store pre-order for UI
            diagnostics["pre_rerank_top_ids"] = pre_rerank_ids
            diagnostics["top_chunk_scores"] = result_scores

            latency_ms = int((time.perf_counter() - t0) * 1000)
            cov = float(diagnostics.get("coverage_score") or 0.0)
            gain = cov - coverage_prev
            coverage_prev = cov

            seq += 1
            step = traces.append_step(
                run_id=run.run_id,
                step_index=seq,
                step_type="retrieval",
                name=f"hybrid_retrieve@iter{i}",
                parent_step_id=root_retrieval_step_id,
                input={
                    "query": q_i,
                    "iteration": i,
                    "k": 6,
                    "alpha": 0.6,
                    "mode": rmode,
                },
                output={
                    "results": [
                        {
                            "chunk_id": r.chunk_id,
                            "doc_id": r.doc_id,
                            "source": r.source,
                            "score": r.score,
                        }
                        for r in results
                    ],
                    "diagnostics": diagnostics,
                    "gain_vs_prev": gain,
                },
                latency_ms=latency_ms,
                score={"coverage_score": cov, "gain": gain},
            )
            if root_retrieval_step_id is None:
                root_retrieval_step_id = step.step_id

            retrieval_timeline.append(
                {
                    "iteration": i,
                    "query": q_i,
                    "coverage_score": cov,
                    "gain": gain,
                    "latency_ms": latency_ms,
                    "rerank": (diagnostics.get("rerank") or {}).get("reranker"),
                    "pre_rerank_top_ids": pre_rerank_ids,
                }
            )

            state["retrieved_contexts"] = _results_to_contexts(results)

            workflows.append_history(
                task_id=task.task_id,
                entry={"type": "retrieval_iteration", "iteration": i, "diagnostics": diagnostics, "gain": gain},
                current_step="retrieve",
            )

            if route.level < 3:
                break
            if cov >= settings.retrieval_target_coverage:
                break
            if i >= 1 and gain < settings.retrieval_min_gain:
                break

    for event in _GRAPH.stream(state):
        for node_name, node_out in event.items():
            seq += 1
            traces.append_step(
                run_id=run.run_id,
                step_index=seq,
                step_type="node",
                name=node_name,
                input={"user_request": user_request, "route": {"label": route.label, "level": route.level}},
                output=node_out if isinstance(node_out, dict) else {"value": node_out},
            )
            workflows.append_history(
                task_id=task.task_id,
                entry={"type": "node", "name": node_name, "output": node_out},
                current_step=node_name,
            )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    workflows.complete_task(task_id=task.task_id, final_decision={"report": state.get("report")})

    steps = traces.list_steps(run.run_id)
    process_metrics, deepeval_info = run_evaluations_for_run(
        user_request=user_request,
        steps=steps,
        report=state.get("report"),
    )
    evals.create_result(
        run_id=run.run_id,
        eval_type="process",
        model=None,
        metrics={
            **process_metrics,
            "retrieval_timeline": retrieval_timeline,
            "retrieval_convergence": {
                "iterations": len(retrieval_timeline),
                "final_coverage": retrieval_timeline[-1]["coverage_score"] if retrieval_timeline else None,
            },
        },
        raw={"deepeval": deepeval_info},
    )
    seq += 1
    eval_step_index = seq
    traces.append_step(
        run_id=run.run_id,
        step_index=eval_step_index,
        step_type="evaluation",
        name="process_metrics",
        input={"run_id": run.run_id},
        output={
            "metrics": {
                **process_metrics,
                "retrieval_timeline": retrieval_timeline,
                "retrieval_convergence": {
                    "iterations": len(retrieval_timeline),
                    "final_coverage": retrieval_timeline[-1]["coverage_score"] if retrieval_timeline else None,
                },
            },
            "deepeval": deepeval_info,
        },
        score=process_metrics,
    )
    seq += 1
    traces.append_step(
        run_id=run.run_id,
        step_index=seq,
        step_type="final",
        name="final",
        input=None,
        output={"report": state.get("report")},
        latency_ms=elapsed_ms,
    )

    return {"run_id": run.run_id, "task_id": task.task_id}
