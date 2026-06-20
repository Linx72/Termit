#!/usr/bin/env python3
"""Validate orchestration eval-slice report against deep/release thresholds."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _apply_tier_from_env() -> int | None:
    tier_name = os.getenv("TERMIT_ORCH_GATE_TIER", "").strip().lower()
    if not tier_name:
        return None
    from app.services.eval_orchestration_gate_tiers import apply_orchestration_gate_tier

    if apply_orchestration_gate_tier(tier_name, overwrite=False) is None:
        print(f"Unknown orchestration gate tier: {tier_name}", file=sys.stderr)
        return 2
    return None


def _as_float(payload: dict[str, object], key: str) -> float:
    return float(payload.get(key, 0.0) or 0.0)


def _build_message(*, tier: str, pass_rate: float, retry_success_rate: float, total: int) -> str:
    return (
        f"Orchestration {tier} gate passed: "
        f"pass_rate={pass_rate:.4f}, retry_success_rate={retry_success_rate:.4f}, total={total}."
    )


def main() -> int:
    tier_error = _apply_tier_from_env()
    if tier_error is not None:
        return tier_error

    report = json.load(sys.stdin)
    tier = os.getenv("TERMIT_ORCH_GATE_TIER", "deep")
    min_pass_rate = float(os.getenv("TERMIT_ORCH_MIN_PASS_RATE", "0.0"))
    min_retry_success_rate = float(os.getenv("TERMIT_ORCH_MIN_RETRY_SUCCESS_RATE", "0.0"))
    min_total = int(os.getenv("TERMIT_ORCH_MIN_TOTAL", "1"))

    pass_rate = _as_float(report, "pass_rate")
    total = int(report.get("total", 0) or 0)
    metrics_after = report.get("metrics_after", {})
    retry_success_rate = 0.0
    if isinstance(metrics_after, dict):
        retry_success_rate = _as_float(metrics_after, "coder_retry_success_rate")

    if total < min_total:
        print(f"Orchestration {tier} gate failed: total={total} < required {min_total}.")
        return 1
    if pass_rate + 1e-9 < min_pass_rate:
        print(
            f"Orchestration {tier} gate failed: pass_rate {pass_rate:.4f} < {min_pass_rate:.4f}."
        )
        return 1
    if retry_success_rate + 1e-9 < min_retry_success_rate:
        print(
            "Orchestration "
            f"{tier} gate failed: retry_success_rate {retry_success_rate:.4f} "
            f"< {min_retry_success_rate:.4f}."
        )
        return 1

    min_tool_steps = max(0, int(os.getenv("TERMIT_ORCH_MIN_TOOL_LOOP_STEPS", "0")))
    if min_tool_steps > 0:
        delta = report.get("delta", {})
        tool_steps_delta = 0.0
        if isinstance(delta, dict):
            tool_steps_delta = float(delta.get("orchestration_tool_steps_total", 0.0) or 0.0)
        if tool_steps_delta + 1e-9 < min_tool_steps:
            print(
                f"Orchestration {tier} gate failed: tool_loop_steps_delta "
                f"{tool_steps_delta:.0f} < {min_tool_steps}."
            )
            return 1

    max_fallback_raw = os.getenv("TERMIT_ORCH_MAX_TOOL_LOOP_FALLBACK_DELTA", "").strip()
    if max_fallback_raw:
        delta = report.get("delta", {})
        fallback_delta = 0.0
        if isinstance(delta, dict):
            fallback_delta = float(delta.get("orchestration_tool_loop_fallback_total", 0.0) or 0.0)
        max_fallback = max(0.0, float(max_fallback_raw))
        if fallback_delta - 1e-9 > max_fallback:
            print(
                f"Orchestration {tier} gate failed: tool_loop_fallback_delta "
                f"{fallback_delta:.0f} > {max_fallback:.0f}."
            )
            return 1

    print(
        _build_message(
            tier=tier,
            pass_rate=pass_rate,
            retry_success_rate=retry_success_rate,
            total=total,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
