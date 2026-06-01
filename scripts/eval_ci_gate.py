#!/usr/bin/env python3
"""Read eval run-suite JSON from stdin and exit non-zero if CI gate fails."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.eval_ci_gate import evaluate_ci_gate, evaluate_finetune_delta_gate


def main() -> int:
    report = json.load(sys.stdin)
    min_rate = float(os.getenv("TERMIT_EVAL_MIN_PASS_RATE", "0.95"))
    min_delta = float(os.getenv("TERMIT_FINETUNE_MIN_EVAL_DELTA", "0"))
    baseline = report.get("baseline_pass_rate")
    baseline_rate = float(baseline) if baseline is not None else None

    if baseline_rate is not None or os.getenv("TERMIT_EVAL_DELTA_GATE", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        ok, message = evaluate_finetune_delta_gate(
            baseline_pass_rate=baseline_rate,
            post_pass_rate=float(report.get("pass_rate", 0.0)),
            total=int(report.get("total", 0)),
            min_delta=min_delta,
            min_rate=min_rate if os.getenv("TERMIT_EVAL_REQUIRE_MIN_RATE", "false").lower() in {"1", "true", "yes"} else None,
        )
    else:
        ok, message = evaluate_ci_gate(
            pass_rate=float(report.get("pass_rate", 0.0)),
            min_rate=min_rate,
            total=int(report.get("total", 0)),
        )
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
