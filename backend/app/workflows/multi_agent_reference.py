from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.core.config import settings
from app.knowledge_engine.compilation.pipeline import compile_knowledge_unit
from app.memory.repository import MemoryRepository
from app.retrieval.hybrid_retriever import hybrid_retrieve
from app.router.adaptive_router import classify_request
from app.tracing.repository import TraceRepository


class MAState(TypedDict, total=False):
    user_request: str
    run_id: str
    route_level: int
    route_label: str
    route_score: float
    budgets: dict[str, Any]
    plan: dict[str, Any]
    retrieved_contexts: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    verification: dict[str, Any]
    memory_id: str | None
    compiled_unit_id: str | None


def _append_agent_step(
    traces: TraceRepository,
    *,
    run_id: str,
    name: str,
    input_payload: dict[str, Any] | None,
    output_payload: dict[str, Any] | None,
    latency_ms: int | None = None,
    step_type: str = "agent",
) -> None:
    idx = traces.next_step_index(run_id)
    traces.append_step(
        run_id=run_id,
        step_index=idx,
        step_type=step_type,
        name=name,
        input=input_payload,
        output=output_payload,
        latency_ms=latency_ms,
    )


def build_planner_subgraph(*, db: Session, run_id: str, traces: TraceRepository):
    def node(state: MAState) -> MAState:
        t0 = time.perf_counter()
        plan = {
            "workflow": "incident_analysis_reference",
            "steps": ["retrieve_evidence", "verify_coverage", "persist_memory", "compile_unit"],
            "notes": {"route": state.get("route_label")},
        }
        out_state = {**state, "plan": plan}
        _append_agent_step(
            traces,
            run_id=run_id,
            name="PlannerSubgraph",
            input_payload={"user_request": state.get("user_request")},
            output_payload={"plan": plan},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        return out_state

    g = StateGraph(MAState)
    g.add_node("plan", node)
    g.set_entry_point("plan")
    g.add_edge("plan", END)
    return g.compile()


def build_retrieval_subgraph(*, db: Session, run_id: str, traces: TraceRepository):
    def node(state: MAState) -> MAState:
        t0 = time.perf_counter()
        q = str(state.get("user_request") or "")
        results, diagnostics = hybrid_retrieve(db=db, query=q, k=6, alpha=0.55, mode="hybrid")
        contexts = [
            {"chunk_id": r.chunk_id, "doc_id": r.doc_id, "text": r.text, "score": r.score} for r in results
        ]
        out_state = {**state, "retrieved_contexts": contexts, "diagnostics": diagnostics}
        _append_agent_step(
            traces,
            run_id=run_id,
            name="RetrievalSubgraph",
            input_payload={"query": q},
            output_payload={"hit_count": len(contexts), "diagnostics": diagnostics},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        return out_state

    g = StateGraph(MAState)
    g.add_node("retrieve", node)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", END)
    return g.compile()


def build_verifier_subgraph(*, db: Session, run_id: str, traces: TraceRepository):
    def node(state: MAState) -> MAState:
        t0 = time.perf_counter()
        diag = state.get("diagnostics") or {}
        cov = float(diag.get("coverage_score") or 0.0)
        ok = cov >= settings.retrieval_target_coverage * 0.85
        verification = {"coverage_score": cov, "passed": ok}
        out_state = {**state, "verification": verification}
        _append_agent_step(
            traces,
            run_id=run_id,
            name="VerifierSubgraph",
            input_payload={"diagnostics": diag},
            output_payload=verification,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        return out_state

    g = StateGraph(MAState)
    g.add_node("verify", node)
    g.set_entry_point("verify")
    g.add_edge("verify", END)
    return g.compile()


def build_memory_subgraph(*, db: Session, run_id: str, traces: TraceRepository):
    def node(state: MAState) -> MAState:
        t0 = time.perf_counter()
        repo = MemoryRepository(db)
        preview = str(state.get("user_request") or "")[:4000]
        item = repo.create_item(
            kind="episodic",
            content=f"Incident analysis notes for request:\n{preview}",
            title="multi-agent episodic note",
            provenance_run_id=run_id,
            created_by="multi_agent_workflow",
        )
        _append_agent_step(
            traces,
            run_id=run_id,
            name="MemorySubgraph",
            input_payload={"user_request_len": len(preview)},
            output_payload={"memory_id": item.memory_id, "status": item.status},
            latency_ms=int((time.perf_counter() - t0) * 1000),
            step_type="memory",
        )
        return {**state, "memory_id": item.memory_id}

    g = StateGraph(MAState)
    g.add_node("memory", node)
    g.set_entry_point("memory")
    g.add_edge("memory", END)
    return g.compile()


def build_compiler_subgraph(*, db: Session, run_id: str, traces: TraceRepository):
    def node(state: MAState) -> MAState:
        t0 = time.perf_counter()
        chunk_ids = [str(c.get("chunk_id")) for c in state.get("retrieved_contexts") or [] if c.get("chunk_id")]
        title = "Compiled operational unit (reference workflow)"
        if chunk_ids:
            unit = compile_knowledge_unit(
                db=db,
                title=title,
                unit_type="procedure",
                query=None,
                chunk_ids=chunk_ids[:40],
                provenance_run_id=run_id,
                confidence=0.7,
                supersedes_unit_id=None,
            )
        else:
            unit = compile_knowledge_unit(
                db=db,
                title=title,
                unit_type="procedure",
                query=str(state.get("user_request") or ""),
                chunk_ids=None,
                provenance_run_id=run_id,
                confidence=0.55,
                supersedes_unit_id=None,
            )
        _append_agent_step(
            traces,
            run_id=run_id,
            name="CompilerSubgraph",
            input_payload={"chunk_ids": chunk_ids},
            output_payload={"unit_id": unit.unit_id},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        return {**state, "compiled_unit_id": unit.unit_id}

    g = StateGraph(MAState)
    g.add_node("compile", node)
    g.set_entry_point("compile")
    g.add_edge("compile", END)
    return g.compile()


def run_multi_agent_incident(*, db: Session, user_request: str) -> dict[str, str]:
    route = classify_request(user_request)
    traces = TraceRepository(db)
    run = traces.create_run(
        workflow_name="multi_agent_incident_reference",
        user_request=user_request,
        route_label=route.label,
    )
    run_id = run.run_id

    base_state: MAState = {
        "user_request": user_request,
        "run_id": run_id,
        "route_level": route.level,
        "route_label": route.label,
        "route_score": route.score,
        "budgets": {
            "max_retrieval_iterations": route.budgets.max_retrieval_iterations,
            "max_workflow_iterations": route.budgets.max_workflow_iterations,
            "max_tools": route.budgets.max_tools,
            "latency_budget_ms": route.budgets.latency_budget_ms,
            "retrieval_mode": route.budgets.retrieval_mode,
        },
    }

    main = StateGraph(MAState)
    main.add_node("planner", build_planner_subgraph(db=db, run_id=run_id, traces=traces))
    main.add_node("retrieval", build_retrieval_subgraph(db=db, run_id=run_id, traces=traces))
    main.add_node("verifier", build_verifier_subgraph(db=db, run_id=run_id, traces=traces))
    main.add_node("memory", build_memory_subgraph(db=db, run_id=run_id, traces=traces))
    main.add_node("compiler", build_compiler_subgraph(db=db, run_id=run_id, traces=traces))

    main.set_entry_point("planner")
    main.add_edge("planner", "retrieval")
    main.add_edge("retrieval", "verifier")
    main.add_edge("verifier", "memory")
    main.add_edge("memory", "compiler")
    main.add_edge("compiler", END)

    graph = main.compile()
    state = graph.invoke(base_state)

    traces.append_step(
        run_id=run_id,
        step_index=traces.next_step_index(run_id),
        step_type="final",
        name="multi_agent_complete",
        input=None,
        output={
            "memory_id": state.get("memory_id"),
            "compiled_unit_id": state.get("compiled_unit_id"),
            "verification": state.get("verification"),
        },
    )

    return {"run_id": run_id}
