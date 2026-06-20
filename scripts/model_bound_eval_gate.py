#!/usr/bin/env python3
"""Run model-bound eval scenarios and apply tier gate (CI-safe or release)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.eval_ci_gate import (
    MODEL_BOUND_CI_GATE,
    MODEL_BOUND_RELEASE_GATE,
    evaluate_tier_gate,
)
from app.services.eval_standalone import build_standalone_eval_service


def main() -> int:
    tier_name = os.getenv("TERMIT_MODEL_BOUND_GATE_TIER", "model_bound_ci").strip().lower()
    gate_map = {
        "model_bound_ci": MODEL_BOUND_CI_GATE,
        "model_bound_release": MODEL_BOUND_RELEASE_GATE,
    }
    selected = gate_map.get(tier_name)
    if selected is None:
        print(f"Unknown model-bound gate tier: {tier_name}", file=sys.stderr)
        return 2

    service = build_standalone_eval_service(root_path=str(ROOT))
    if tier_name == "model_bound_release":
        scenario_ids = service.model_bound_scenario_ids()
    else:
        scenario_ids = service.model_bound_tool_scenario_ids()

    report = service.run_scenario_ids(
        scenario_ids,
        persist_report=False,
        category_filter="model_bound",
    )
    ok, message = evaluate_tier_gate(
        tier=selected,
        pass_rate=float(report["pass_rate"]),
        total=int(report["total"]),
        quality_median=float(report.get("quality_median") or 0.0),
        cloud_judge_coverage=float(report.get("cloud_judge_coverage") or 0.0),
    )
    print(json.dumps({"gate": tier_name, "ok": ok, "message": message, "report": report}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
