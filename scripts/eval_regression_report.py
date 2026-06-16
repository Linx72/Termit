#!/usr/bin/env python3
"""Compare eval suite reports and fail on pass-rate regression."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _scenario_key(item: dict[str, Any]) -> str:
    for key in ("id", "scenario_id", "name"):
        value = str(item.get(key, "")).strip()
        if value:
            return value
    prompt = str(item.get("prompt", "")).strip()
    return prompt[:80] or "unknown"


def _failed_ids(report: dict[str, Any]) -> set[str]:
    results = report.get("results", [])
    if not isinstance(results, list):
        return set()
    failed: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).strip().lower()
        if status != "passed":
            failed.add(_scenario_key(item))
    return failed


def compare_eval_reports(
    *,
    baseline: dict[str, Any],
    current: dict[str, Any],
    max_pass_rate_drop: float,
) -> tuple[bool, dict[str, Any]]:
    baseline_rate = float(baseline.get("pass_rate", 0.0) or 0.0)
    current_rate = float(current.get("pass_rate", 0.0) or 0.0)
    delta = round(current_rate - baseline_rate, 4)
    baseline_failed = _failed_ids(baseline)
    current_failed = _failed_ids(current)
    new_failures = sorted(current_failed - baseline_failed)
    fixed = sorted(baseline_failed - current_failed)
    ok = delta + 1e-9 >= -abs(max_pass_rate_drop)
    payload = {
        "baseline_pass_rate": baseline_rate,
        "current_pass_rate": current_rate,
        "pass_rate_delta": delta,
        "max_pass_rate_drop": max_pass_rate_drop,
        "new_failures": new_failures,
        "fixed_failures": fixed,
        "baseline_total": int(baseline.get("total", 0) or 0),
        "current_total": int(current.get("total", 0) or 0),
        "gate_passed": ok,
    }
    return ok, payload


def _load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Report must be a JSON object: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval regression gate vs baseline report")
    parser.add_argument("--baseline", required=True, help="Baseline eval report JSON path")
    parser.add_argument("--current", required=True, help="Current eval report JSON path")
    parser.add_argument(
        "--max-pass-rate-drop",
        type=float,
        default=0.02,
        help="Allowed pass_rate drop vs baseline (default 0.02)",
    )
    parser.add_argument("--output", default="", help="Optional JSON summary output path")
    args = parser.parse_args()

    baseline = _load_report(Path(args.baseline))
    current = _load_report(Path(args.current))
    ok, summary = compare_eval_reports(
        baseline=baseline,
        current=current,
        max_pass_rate_drop=max(0.0, float(args.max_pass_rate_drop)),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.output:
        Path(args.output).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not ok:
        print(
            "Eval regression gate failed: "
            f"pass_rate dropped by {abs(summary['pass_rate_delta']):.4f} "
            f"(limit {summary['max_pass_rate_drop']:.4f}).",
            file=sys.stderr,
        )
        if summary["new_failures"]:
            print(f"New failures: {', '.join(summary['new_failures'][:10])}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
