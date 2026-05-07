from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.core.config import settings
from app.router.adaptive_router import RouteDecision
from app.retrieval.hybrid_retriever import hybrid_retrieve
from app.evaluation.hook import run_evaluations_for_run
from app.evaluation.repository import EvaluationRepository
from app.state_management.repository import WorkflowRepository
from app.tracing.repository import TraceRepository


def _rewrite_query_heuristic(original: str, iteration: int) -> str:
    """
    Deterministic query evolution (MVP).
    Later replaced with LLM-based rewrite + decomposition policy.
    """
    base = original.strip()
    if iteration <= 0:
        return base
    if iteration == 1:
        return f"{base} key details evidence"
    return f"{base} constraints edge cases citations"


class ADWState(TypedDict, total=False):
    user_request: str
    route_label: str
    route_score: float
    route_reasons: list[str]

    plan: dict[str, Any]
    retrieved_contexts: list[dict[str, Any]]
    reasoning_trace: list[dict[str, Any]]
    report: dict[str, Any]


def _node_plan(state: ADWState) -> ADWState:
    # Deterministic placeholder planner; later replaced by planner agent + constraints.
    req = state["user_request"]
    plan = {
        "objective": "produce actionable output grounded in retrieved evidence",
        "steps": [
            {"name": "decompose", "description": "derive sub-questions if needed"},
            {"name": "retrieve", "description": "hybrid retrieval + rerank (stubbed)"},
            {"name": "synthesize", "description": "compose report with citations"},
        ],
        "notes": {"input_length": len(req)},
    }
    state["plan"] = plan
    return state


def _node_retrieve(state: ADWState) -> ADWState:
    # Retrieval execution runs outside the graph node (needs DB/trace injection),
    # so this node is now a no-op placeholder that keeps graph structure stable.
    # The orchestrator will populate `retrieved_contexts`.
    state["retrieved_contexts"] = state.get("retrieved_contexts", [])
    return state


def _node_reason(state: ADWState) -> ADWState:
    # Reasoning trace should be inspectable: store structured thought-free trajectory events.
    trace = state.get("reasoning_trace", [])
    trace.append(
        {
            "type": "reflection",
            "content": "MVP: reasoning agent is stubbed; next adds constrained multi-hop reasoning.",
        }
    )
    state["reasoning_trace"] = trace
    return state


def _node_report(state: ADWState) -> ADWState:
    report = {
        "kind": "adw_report",
        "summary": "ADW orchestration skeleton executed. Replace stubs with retrieval + agents next.",
        "route": {
            "label": state.get("route_label"),
            "score": state.get("route_score"),
            "reasons": state.get("route_reasons"),
        },
        "citations": [
            {"doc_id": c["doc_id"], "chunk_id": c["chunk_id"], "source": c["source"]}
            for c in state.get("retrieved_contexts", [])
        ],
    }
    state["report"] = report
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

    run = traces.create_run(workflow_name="adw_orchestrator", user_request=user_request, route_label=route.label)
    task = workflows.create_task(user_request=user_request, route_label=route.label, run_id=run.run_id)

    state: ADWState = {
        "user_request": user_request,
        "route_label": route.label,
        "route_score": route.score,
        "route_reasons": route.reasons,
        "retrieved_contexts": [],
        "reasoning_trace": [],
    }

    step_index = 0
    start = time.perf_counter()

    # Iterative retrieval loop (instrumented)
    root_retrieval_step_id: str | None = None
    coverage_prev = 0.0
    retrieval_timeline: list[dict[str, Any]] = []

    for i in range(settings.max_retrieval_iterations):
        q_i = _rewrite_query_heuristic(user_request, i)
        t0 = time.perf_counter()
        results, diagnostics = hybrid_retrieve(db=db, query=q_i, k=6, alpha=0.6)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        cov = float(diagnostics.get("coverage_score") or 0.0)
        gain = cov - coverage_prev
        coverage_prev = cov

        step = traces.append_step(
            run_id=run.run_id,
            step_index=1 + i,
            step_type="retrieval",
            name=f"hybrid_retrieve@iter{i}",
            parent_step_id=root_retrieval_step_id,
            input={"query": q_i, "iteration": i, "k": 6, "alpha": 0.6},
            output={
                "results": [
                    {"chunk_id": r.chunk_id, "doc_id": r.doc_id, "source": r.source, "score": r.score}
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
        else:
            # parent all later iterations to root so the UI draws an iteration chain
            pass

        retrieval_timeline.append(
            {
                "iteration": i,
                "query": q_i,
                "coverage_score": cov,
                "gain": gain,
                "latency_ms": latency_ms,
                "rerank": (diagnostics.get("rerank") or {}).get("reranker"),
            }
        )

        # Update state with best-so-far contexts (latest iteration for MVP)
        state["retrieved_contexts"] = [
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

        workflows.append_history(
            task_id=task.task_id,
            entry={"type": "retrieval_iteration", "iteration": i, "diagnostics": diagnostics, "gain": gain},
            current_step="retrieve",
        )

        # Stopping conditions
        if cov >= settings.retrieval_target_coverage:
            break
        if i >= 1 and gain < settings.retrieval_min_gain:
            break

    for event in _GRAPH.stream(state):
        # event looks like {"node_name": {"state_delta": ...}} in langgraph stream
        for node_name, node_out in event.items():
            # retrieval loop used indices 1..N
            step_index += 1
            effective_index = step_index + 1 + len(retrieval_timeline)
            traces.append_step(
                run_id=run.run_id,
                step_index=effective_index,
                step_type="node",
                name=node_name,
                input={"user_request": user_request, "route": {"label": route.label, "score": route.score}},
                output=node_out if isinstance(node_out, dict) else {"value": node_out},
            )

            workflows.append_history(
                task_id=task.task_id,
                entry={"type": "node", "name": node_name, "output": node_out},
                current_step=node_name,
            )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    workflows.complete_task(task_id=task.task_id, final_decision={"report": state.get("report")})

    # Evaluation hook (process-first). DeepEval is optional and safe to enable later.
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
    traces.append_step(
        run_id=run.run_id,
        step_index=step_index + 2,
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
    traces.append_step(
        run_id=run.run_id,
        step_index=step_index + 3,
        step_type="final",
        name="final",
        input=None,
        output={"report": state.get("report")},
        latency_ms=elapsed_ms,
    )

    return {"run_id": run.run_id, "task_id": task.task_id}

