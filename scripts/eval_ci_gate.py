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

from app.services.eval_ci_gate import DEEP_GATE, FAST_GATE, MODEL_BOUND_CI_GATE, MODEL_BOUND_RELEASE_GATE, RELEASE_GATE, evaluate_ci_gate, evaluate_tier_gate


def main() -> int:
    report = json.load(sys.stdin)
    tier_name = os.getenv("TERMIT_EVAL_GATE_TIER", "").strip().lower()
    gate_map = {
        "fast": FAST_GATE,
        "deep": DEEP_GATE,
        "release": RELEASE_GATE,
        "model_bound_ci": MODEL_BOUND_CI_GATE,
        "model_bound_release": MODEL_BOUND_RELEASE_GATE,
    }
    selected = gate_map.get(tier_name)
    if selected is None:
        min_rate = float(os.getenv("TERMIT_EVAL_MIN_PASS_RATE", "0.95"))
        ok, message = evaluate_ci_gate(
            pass_rate=float(report.get("pass_rate", 0.0)),
            min_rate=min_rate,
            total=int(report.get("total", 0)),
        )
    else:
        ok, message = evaluate_tier_gate(
            tier=selected,
            pass_rate=float(report.get("pass_rate", 0.0)),
            total=int(report.get("total", 0)),
            quality_median=float(report.get("quality_median", 0.0) or 0.0) or None,
            cloud_judge_coverage=float(report.get("cloud_judge_coverage", 0.0) or 0.0),
        )
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
