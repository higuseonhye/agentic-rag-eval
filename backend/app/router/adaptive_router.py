from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteBudgets:
    """Execution budgets selected by the adaptive router."""

    max_retrieval_iterations: int
    max_workflow_iterations: int
    max_tools: int
    latency_budget_ms: int | None
    use_graph: bool
    retrieval_mode: str  # dense_only | sparse_only | hybrid


@dataclass(frozen=True)
class RouteDecision:
    """
    Adaptive routing levels:
      L0 — no retrieval (direct response path)
      L1 — semantic / dense retrieval only
      L2 — hybrid retrieval + reranking
      L3 — agentic RAG (iterative retrieval + reflection hooks)
      L4 — full ADW (stateful workflow + graph + structured outputs)
    """

    level: int  # 0..4
    label: str  # L0..L4
    score: float  # 0..1 complexity
    reasons: list[str]
    budgets: RouteBudgets


_NO_RETRIEVAL_PATTERNS: list[tuple[str, str]] = [
    (r"^(hi|hello|hey)\b", "greeting"),
    (r"^(thanks|thank you)\b", "thanks"),
    (r"^what('s| is) your name\b", "meta_chat"),
]

_COMPLEX_PATTERNS: list[tuple[str, str]] = [
    (r"\b(compare|contrast|trade-?off|pros?\s+and\s+cons)\b", "comparison intent"),
    (r"\b(plan|roadmap|workflow|pipeline|procedure|step[-\s]?by[-\s]?step)\b", "workflow intent"),
    (r"\b(analyze|investigate|root cause|incident)\b", "analysis intent"),
    (r"\b(compliance|policy|audit|regulation)\b", "compliance intent"),
    (r"\b(contract|msa|sla|clause|liability|indemnif)\b", "contract intent"),
    (r"\b(multi[-\s]?hop|cross[-\s]?reference|multiple documents?)\b", "multi-doc reasoning"),
    (r"\b(generate|produce|draft)\b.+\b(report|checklist|memo|decision)\b", "actionable output"),
    (r"\b(approve|approval|sign[- ]?off|audit trail)\b", "enterprise_workflow"),
]


def classify_request(user_request: str) -> RouteDecision:
    text = user_request.strip()
    reasons: list[str] = []
    score = 0.0

    lowered = text.lower()

    # L0: explicit no-doc / chitchat (short)
    if len(text) < 120:
        for pattern, reason in _NO_RETRIEVAL_PATTERNS:
            if re.search(pattern, lowered):
                return RouteDecision(
                    level=0,
                    label="L0",
                    score=0.0,
                    reasons=[reason],
                    budgets=RouteBudgets(
                        max_retrieval_iterations=0,
                        max_workflow_iterations=1,
                        max_tools=0,
                        latency_budget_ms=5000,
                        use_graph=False,
                        retrieval_mode="dense_only",
                    ),
                )

    # Complexity signals
    if len(text) > 280:
        score += 0.15
        reasons.append("long request")
    if text.count("\n") >= 4:
        score += 0.10
        reasons.append("multi-part structure")
    if sum(1 for _ in re.finditer(r"\b(and|then|also|additionally)\b", lowered)) >= 3:
        score += 0.10
        reasons.append("multi-intent phrasing")
    if "?" in text and text.count("?") >= 2:
        score += 0.10
        reasons.append("multiple questions")

    workflow_trigger = False
    for pattern, reason in _COMPLEX_PATTERNS:
        if re.search(pattern, lowered):
            score += 0.12
            reasons.append(reason)
            if reason in ("workflow intent", "enterprise_workflow", "contract intent"):
                workflow_trigger = True

    score = max(0.0, min(1.0, score))
    if not reasons:
        reasons = ["default"]

    # Map score + triggers to L1–L4
    if score < 0.18:
        level, label, mode = 1, "L1", "dense_only"
        max_ret, max_wf, tools, graph = 1, 2, 4, False
    elif score < 0.45:
        level, label, mode = 2, "L2", "hybrid"
        max_ret, max_wf, tools, graph = 1, 3, 8, False
    elif score < 0.72 or not workflow_trigger:
        level, label, mode = 3, "L3", "hybrid"
        max_ret, max_wf, tools, graph = 3, 6, 16, True
    else:
        level, label, mode = 4, "L4", "hybrid"
        max_ret, max_wf, tools, graph = 4, 8, 20, True

    return RouteDecision(
        level=level,
        label=label,
        score=score,
        reasons=reasons,
        budgets=RouteBudgets(
            max_retrieval_iterations=max_ret,
            max_workflow_iterations=max_wf,
            max_tools=tools,
            latency_budget_ms=None,
            use_graph=graph,
            retrieval_mode=mode,
        ),
    )
