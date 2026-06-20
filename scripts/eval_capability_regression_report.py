#!/usr/bin/env python3
"""Compare capability-review report against baseline and fail on regression."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _as_float(payload: dict[str, Any], key: str) -> float:
    return float(payload.get(key, 0.0) or 0.0)


def _as_int(payload: dict[str, Any], key: str) -> int:
    return int(payload.get(key, 0) or 0)


def compare_capability_reports(
    *,
    baseline: dict[str, Any],
    current: dict[str, Any],
    max_pass_gap_drop: float,
    max_quality_gap_drop: float,
    max_win_rate_drop: float,
) -> tuple[bool, dict[str, Any]]:
    baseline_pass_gap = _as_float(baseline, "mean_pass_gap")
    current_pass_gap = _as_float(current, "mean_pass_gap")
    baseline_quality_gap = _as_float(baseline, "mean_quality_gap")
    current_quality_gap = _as_float(current, "mean_quality_gap")
    baseline_win_rate = _as_float(baseline, "termit_win_rate")
    current_win_rate = _as_float(current, "termit_win_rate")

    pass_gap_delta = round(current_pass_gap - baseline_pass_gap, 4)
    quality_gap_delta = round(current_quality_gap - baseline_quality_gap, 4)
    win_rate_delta = round(current_win_rate - baseline_win_rate, 4)

    baseline_reports = _as_int(baseline, "total_reports")
    current_reports = _as_int(current, "total_reports")
    min_reports = max(1, baseline_reports)

    # На CI runner без eval_reports.jsonl — не блокировать extended smoke.
    tier = os.getenv("TERMIT_CAP_GATE_TIER", "").strip().lower()
    if tier == "ci" and current_reports == 0:
        payload = {
            "baseline_total_reports": baseline_reports,
            "current_total_reports": 0,
            "required_min_reports": min_reports,
            "baseline_mean_pass_gap": _as_float(baseline, "mean_pass_gap"),
            "current_mean_pass_gap": 0.0,
            "mean_pass_gap_delta": 0.0,
            "max_pass_gap_drop": max_pass_gap_drop,
            "baseline_mean_quality_gap": _as_float(baseline, "mean_quality_gap"),
            "current_mean_quality_gap": 0.0,
            "mean_quality_gap_delta": 0.0,
            "max_quality_gap_drop": max_quality_gap_drop,
            "baseline_termit_win_rate": _as_float(baseline, "termit_win_rate"),
            "current_termit_win_rate": 0.0,
            "termit_win_rate_delta": 0.0,
            "max_win_rate_drop": max_win_rate_drop,
            "current_trend_direction": "no_data",
            "allowed_trend_directions": ["flat", "improving"],
            "gate_passed": True,
            "notes": ["No benchmark history on runner — CI regression gate skipped."],
        }
        return True, payload

    trend = str(current.get("trend_direction", "no_data")).strip().lower()
    trend_ok = trend in {"flat", "improving"}

    ok = (
        current_reports >= min_reports
        and pass_gap_delta + 1e-9 >= -abs(max_pass_gap_drop)
        and quality_gap_delta + 1e-9 >= -abs(max_quality_gap_drop)
        and win_rate_delta + 1e-9 >= -abs(max_win_rate_drop)
        and trend_ok
    )

    payload = {
        "baseline_total_reports": baseline_reports,
        "current_total_reports": current_reports,
        "required_min_reports": min_reports,
        "baseline_mean_pass_gap": baseline_pass_gap,
        "current_mean_pass_gap": current_pass_gap,
        "mean_pass_gap_delta": pass_gap_delta,
        "max_pass_gap_drop": max_pass_gap_drop,
        "baseline_mean_quality_gap": baseline_quality_gap,
        "current_mean_quality_gap": current_quality_gap,
        "mean_quality_gap_delta": quality_gap_delta,
        "max_quality_gap_drop": max_quality_gap_drop,
        "baseline_termit_win_rate": baseline_win_rate,
        "current_termit_win_rate": current_win_rate,
        "termit_win_rate_delta": win_rate_delta,
        "max_win_rate_drop": max_win_rate_drop,
        "current_trend_direction": trend,
        "allowed_trend_directions": ["flat", "improving"],
        "gate_passed": ok,
    }
    return ok, payload


def _load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Report must be JSON object: {path}")
    return data


def _apply_tier_from_env() -> int | None:
    tier_name = os.getenv("TERMIT_CAP_GATE_TIER", "").strip().lower()
    if not tier_name:
        return None
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from app.services.eval_capability_gate_tiers import apply_capability_gate_tier

    if apply_capability_gate_tier(tier_name) is None:
        print(f"Unknown capability gate tier: {tier_name}", file=sys.stderr)
        return 2
    return None


def main() -> int:
    tier_error = _apply_tier_from_env()
    if tier_error is not None:
        return tier_error

    parser = argparse.ArgumentParser(description="Capability-review regression gate")
    parser.add_argument("--baseline", required=True, help="Baseline capability-review JSON path")
    parser.add_argument("--current", required=True, help="Current capability-review JSON path")
    parser.add_argument(
        "--max-pass-gap-drop",
        type=float,
        default=float(os.getenv("TERMIT_CAP_REG_MAX_PASS_GAP_DROP", "0.05")),
    )
    parser.add_argument(
        "--max-quality-gap-drop",
        type=float,
        default=float(os.getenv("TERMIT_CAP_REG_MAX_QUALITY_GAP_DROP", "0.05")),
    )
    parser.add_argument(
        "--max-win-rate-drop",
        type=float,
        default=float(os.getenv("TERMIT_CAP_REG_MAX_WIN_RATE_DROP", "0.10")),
    )
    parser.add_argument("--output", default="", help="Optional JSON summary output path")
    args = parser.parse_args()

    baseline = _load_report(Path(args.baseline))
    current = _load_report(Path(args.current))
    ok, summary = compare_capability_reports(
        baseline=baseline,
        current=current,
        max_pass_gap_drop=max(0.0, float(args.max_pass_gap_drop)),
        max_quality_gap_drop=max(0.0, float(args.max_quality_gap_drop)),
        max_win_rate_drop=max(0.0, float(args.max_win_rate_drop)),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.output:
        Path(args.output).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not ok:
        print("Capability regression gate failed.", file=sys.stderr)
        if summary["current_total_reports"] < summary["required_min_reports"]:
            print(
                f"Not enough reports: {summary['current_total_reports']} < {summary['required_min_reports']}",
                file=sys.stderr,
            )
        if summary["mean_pass_gap_delta"] + 1e-9 < -summary["max_pass_gap_drop"]:
            print(
                "mean_pass_gap regression: "
                f"{summary['mean_pass_gap_delta']:.4f} < -{summary['max_pass_gap_drop']:.4f}",
                file=sys.stderr,
            )
        if summary["mean_quality_gap_delta"] + 1e-9 < -summary["max_quality_gap_drop"]:
            print(
                "mean_quality_gap regression: "
                f"{summary['mean_quality_gap_delta']:.4f} < -{summary['max_quality_gap_drop']:.4f}",
                file=sys.stderr,
            )
        if summary["termit_win_rate_delta"] + 1e-9 < -summary["max_win_rate_drop"]:
            print(
                "termit_win_rate regression: "
                f"{summary['termit_win_rate_delta']:.4f} < -{summary['max_win_rate_drop']:.4f}",
                file=sys.stderr,
            )
        if summary["current_trend_direction"] not in {"flat", "improving"}:
            print(
                f"Trend not allowed: {summary['current_trend_direction']}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
