from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    label: str  # "simple" | "complex"
    score: float  # 0..1 (complexity)
    reasons: list[str]


_COMPLEX_PATTERNS: list[tuple[str, str]] = [
    (r"\b(compare|contrast|trade-?off|pros?\s+and\s+cons)\b", "comparison intent"),
    (r"\b(plan|roadmap|workflow|pipeline|procedure|step[-\s]?by[-\s]?step)\b", "workflow intent"),
    (r"\b(analyze|investigate|root cause|incident)\b", "analysis intent"),
    (r"\b(compliance|policy|audit|regulation)\b", "compliance intent"),
    (r"\b(contract|msa|sla|clause|liability|indemnif)\b", "contract intent"),
    (r"\b(multi[-\s]?hop|cross[-\s]?reference|multiple documents?)\b", "multi-doc reasoning"),
    (r"\b(generate|produce|draft)\b.+\b(report|checklist|memo|decision)\b", "actionable output"),
]


def classify_request(user_request: str) -> RouteDecision:
    text = user_request.strip()
    reasons: list[str] = []
    score = 0.0

    # Heuristic signals (fast + deterministic)
    if len(text) > 280:
        score += 0.15
        reasons.append("long request")
    if text.count("\n") >= 4:
        score += 0.10
        reasons.append("multi-part structure")
    if sum(1 for _ in re.finditer(r"\b(and|then|also|additionally)\b", text.lower())) >= 3:
        score += 0.10
        reasons.append("multi-intent phrasing")
    if "?" in text and text.count("?") >= 2:
        score += 0.10
        reasons.append("multiple questions")

    lowered = text.lower()
    for pattern, reason in _COMPLEX_PATTERNS:
        if re.search(pattern, lowered):
            score += 0.12
            reasons.append(reason)

    score = max(0.0, min(1.0, score))
    label = "complex" if score >= 0.45 else "simple"
    if not reasons:
        reasons = ["default"]
    return RouteDecision(label=label, score=score, reasons=reasons)

