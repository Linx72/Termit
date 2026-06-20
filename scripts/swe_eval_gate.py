#!/usr/bin/env python3
"""Run SWE-bench-style offline fixture scenarios (tool_patch_verify)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.eval_service import EvalService
from app.services.tooling_service import ToolingService

SWE_MIN_PASS_RATE = 1.0


def main() -> int:
    settings = get_settings()
    swe_path = Path(settings.eval_swe_scenarios_path)
    if not swe_path.is_file():
        print(f"SWE scenarios file not found: {swe_path}", file=sys.stderr)
        return 2

    tooling = ToolingService(root_path=str(ROOT))
    service = EvalService(
        scenarios_path=str(swe_path),
        tooling_service=tooling,
    )
    scenarios = service.list_scenarios()
    scenario_ids = [item.id for item in scenarios if str(item.id).startswith("SWE")]
    if not scenario_ids:
        print("No SWE scenarios found.", file=sys.stderr)
        return 2

    report = service.run_scenario_ids(scenario_ids, persist_report=False, category_filter="swe_bench")
    total = int(report.get("total", 0))
    pass_rate = float(report.get("pass_rate", 0.0))
    min_rate = float(os.getenv("TERMIT_SWE_GATE_MIN_PASS_RATE", str(SWE_MIN_PASS_RATE)))
    ok = total > 0 and pass_rate + 1e-9 >= min_rate
    message = (
        f"SWE gate {'passed' if ok else 'failed'}: pass_rate={pass_rate:.4f}, "
        f"total={total}, min={min_rate:.4f}."
    )
    print(json.dumps({"gate_passed": ok, "scenario_ids": scenario_ids, "pass_rate": pass_rate}, indent=2))
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
