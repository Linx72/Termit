#!/usr/bin/env python3
"""Evaluate +N% eval pass improvement KPI after finetune / stage1 cycle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def _pass_rate_from_report(payload: dict[str, object]) -> Optional[float]:
    if "pass_rate" in payload:
        return float(payload["pass_rate"])
    results = payload.get("results")
    if isinstance(results, list) and results:
        passed = sum(1 for row in results if row.get("passed"))
        return passed / len(results)
    return None


def evaluate_improvement_kpi(
    *,
    baseline_pass_rate: Optional[float],
    current_pass_rate: Optional[float],
    min_improvement: float,
) -> dict[str, object]:
    """Return KPI summary for post-train eval vs baseline."""
    summary: dict[str, object] = {
        "baseline_pass_rate": baseline_pass_rate,
        "current_pass_rate": current_pass_rate,
        "min_improvement_required": min_improvement,
        "delta": None,
        "kpi_passed": False,
        "reason": "",
    }
    if current_pass_rate is None:
        summary["reason"] = "Current eval pass_rate missing; KPI not measured."
        return summary
    if baseline_pass_rate is None:
        summary["reason"] = "Baseline pass_rate missing; KPI not measured."
        return summary

    delta = current_pass_rate - baseline_pass_rate
    summary["delta"] = delta
    passed = delta + 1e-9 >= min_improvement
    summary["kpi_passed"] = passed
    if passed:
        summary["reason"] = f"KPI met: improvement {delta:+.2%} >= {min_improvement:.2%}."
    else:
        summary["reason"] = (
            f"KPI not met: improvement {delta:+.2%} below target {min_improvement:.2%}."
        )
    return summary


def load_baseline_rate(path: Path) -> Optional[float]:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _pass_rate_from_report(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check +N% eval pass improvement KPI")
    parser.add_argument("--baseline", help="Baseline eval JSON path")
    parser.add_argument("--baseline-rate", type=float, default=None)
    parser.add_argument("--current", help="Current eval JSON path")
    parser.add_argument("--current-rate", type=float, default=None)
    parser.add_argument(
        "--min-improvement",
        type=float,
        default=float(__import__("os").getenv("TERMIT_FINETUNE_MIN_EVAL_IMPROVEMENT", "0.05")),
    )
    parser.add_argument("--strict", action="store_true", help="Exit 1 when KPI not met")
    parser.add_argument(
        "--dev-only",
        action="store_true",
        help="Mark KPI JSON as dev-only fixture (CI plan-status check).",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    baseline_rate = args.baseline_rate
    if baseline_rate is None and args.baseline:
        baseline_rate = load_baseline_rate(Path(args.baseline))

    current_rate = args.current_rate
    if current_rate is None and args.current:
        current_payload = json.loads(Path(args.current).read_text(encoding="utf-8"))
        current_rate = _pass_rate_from_report(current_payload)

    summary = evaluate_improvement_kpi(
        baseline_pass_rate=baseline_rate,
        current_pass_rate=current_rate,
        min_improvement=max(0.0, float(args.min_improvement)),
    )
    if args.dev_only:
        summary["dev_only"] = True
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.output:
        Path(args.output).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.strict and not summary.get("kpi_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
