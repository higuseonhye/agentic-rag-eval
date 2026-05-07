from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.evaluation.process_metrics import compute_process_metrics


def run_evaluations_for_run(
    *,
    user_request: str,
    steps: list[dict[str, Any]],
    report: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    MVP evaluation hook:
    - Always compute deterministic process metrics.
    - DeepEval integration is wired as a safe optional path (no hard dependency on keys).
    """
    process_metrics = compute_process_metrics(steps=steps)

    deepeval_info: dict[str, Any] = {
        "enabled": bool(settings.llm_api_key and settings.llm_base_url),
        "model": settings.llm_model,
        "note": "DeepEval judge wiring is scaffolded; enable by setting LLM_* env vars.",
    }

    # We intentionally keep the DeepEval call out of MVP until LLM config + metric selection are finalized.
    # This function returns both metrics and raw artifacts so they can be persisted.
    return process_metrics, deepeval_info

