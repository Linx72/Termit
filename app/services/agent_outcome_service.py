"""Classify agent run outcomes for autonomy metrics and UX."""

from __future__ import annotations

from typing import Optional


OUTCOME_SUCCESS = "success"
OUTCOME_PARTIAL = "partial"
OUTCOME_BLOCKED_EXTERNAL = "blocked-external"
OUTCOME_BLOCKED_POLICY = "blocked-policy"
OUTCOME_FAILED = "failed"


def agent_run_success_rate(by_outcome_class: dict[str, int] | None) -> tuple[float, int]:
    """Доля terminal runs с outcome success (для KPI gate Day 90)."""
    if not by_outcome_class:
        return 0.0, 0
    terminal = sum(int(count) for count in by_outcome_class.values())
    if terminal <= 0:
        return 0.0, 0
    success = int(by_outcome_class.get(OUTCOME_SUCCESS, 0) or 0)
    return round(success / terminal, 4), terminal


def classify_agent_outcome(
    *,
    state: str,
    failure_class: Optional[str],
    response: str,
    error: Optional[str],
    events: Optional[list[dict[str, str]]] = None,
) -> str:
    """Map run terminal state to product outcome class."""
    normalized_state = (state or "").strip().lower()
    if normalized_state == "completed":
        text = (response or "").strip().lower()
        if any(marker in text for marker in ("partial", "could not complete", "blocked by")):
            return OUTCOME_PARTIAL
        return OUTCOME_SUCCESS

    fc = (failure_class or "").strip().lower()
    if fc in {"user_rejected", "safety_block", "phase_guard_blocked"}:
        return OUTCOME_BLOCKED_POLICY
    if fc in {"run_timeout", "external_error", "provider_error"}:
        return OUTCOME_BLOCKED_EXTERNAL
    if fc in {"verification_error", "tool_error", "parse_error", "step_limit"}:
        return OUTCOME_PARTIAL

    event_text = " ".join(
        str(item.get("message", "")) for item in (events or []) if isinstance(item, dict)
    ).lower()
    if "blocked" in event_text and "policy" in event_text:
        return OUTCOME_BLOCKED_POLICY
    if "timeout" in event_text or "external" in event_text:
        return OUTCOME_BLOCKED_EXTERNAL
    if error:
        err = error.lower()
        if "policy" in err or "confirm" in err or "rejected" in err:
            return OUTCOME_BLOCKED_POLICY
        if "timeout" in err or "unreachable" in err or "connection" in err:
            return OUTCOME_BLOCKED_EXTERNAL

    return OUTCOME_FAILED
