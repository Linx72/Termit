#!/usr/bin/env python3
"""Validate orchestration eval-slice report against deep/release thresholds."""

from __future__ import annotations

import json
import os
import sys


def _as_float(payload: dict[str, object], key: str) -> float:
    return float(payload.get(key, 0.0) or 0.0)


def _build_message(*, tier: str, pass_rate: float, retry_success_rate: float, total: int) -> str:
    return (
        f"Orchestration {tier} gate passed: "
        f"pass_rate={pass_rate:.4f}, retry_success_rate={retry_success_rate:.4f}, total={total}."
    )


def main() -> int:
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
