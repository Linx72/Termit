#!/usr/bin/env python3
"""Compare flaky-watch reports and compute trend deltas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _suite_index(report: dict[str, object]) -> dict[str, dict[str, object]]:
    index: dict[str, dict[str, object]] = {}
    for row in report.get("suites", []):
        if isinstance(row, dict):
            name = str(row.get("suite", "")).strip()
            if name:
                index[name] = row
    return index


def _suite_trend_label(*, pass_rate_delta: float | None, duration_delta: float | None) -> str:
    if pass_rate_delta is None:
        return "unknown"
    if pass_rate_delta > 0:
        return "improved"
    if pass_rate_delta < 0:
        return "regressed"
    if duration_delta is None:
        return "stable"
    if duration_delta < -0.05:
        return "improved"
    if duration_delta > 0.05:
        return "regressed"
    return "stable"


def build_trend(
    current: dict[str, object],
    baseline: dict[str, object] | None,
    *,
    baseline_status: str = "available",
    baseline_note: str = "",
) -> dict[str, object]:
    current_idx = _suite_index(current)
    baseline_idx = _suite_index(baseline or {})
    rows: list[dict[str, object]] = []
    improved_count = 0
    regressed_count = 0
    stable_count = 0
    for suite_name in sorted(current_idx.keys()):
        now = current_idx[suite_name]
        prev = baseline_idx.get(suite_name)
        current_pass_rate = float(now.get("pass_rate", 0.0) or 0.0)
        current_mean = float(now.get("duration_mean_seconds", 0.0) or 0.0)
        baseline_pass_rate = float(prev.get("pass_rate", 0.0) or 0.0) if prev else None
        baseline_mean = float(prev.get("duration_mean_seconds", 0.0) or 0.0) if prev else None
        pass_delta = (
            round(current_pass_rate - baseline_pass_rate, 4) if baseline_pass_rate is not None else None
        )
        duration_delta = round(current_mean - baseline_mean, 4) if baseline_mean is not None else None
        trend_label = _suite_trend_label(pass_rate_delta=pass_delta, duration_delta=duration_delta)
        if trend_label == "improved":
            improved_count += 1
        elif trend_label == "regressed":
            regressed_count += 1
        elif trend_label == "stable":
            stable_count += 1
        rows.append(
            {
                "suite": suite_name,
                "trend": trend_label,
                "current_pass_rate": current_pass_rate,
                "baseline_pass_rate": baseline_pass_rate,
                "pass_rate_delta": pass_delta,
                "current_duration_mean_seconds": current_mean,
                "baseline_duration_mean_seconds": baseline_mean,
                "duration_mean_delta_seconds": duration_delta,
            }
        )
    overall_trend = "stable"
    if regressed_count > 0:
        overall_trend = "regressed"
    elif improved_count > 0:
        overall_trend = "improved"
    return {
        "baseline_available": baseline is not None,
        "baseline_status": baseline_status,
        "baseline_note": baseline_note,
        "overall_trend": overall_trend,
        "improved_suites": improved_count,
        "regressed_suites": regressed_count,
        "stable_suites": stable_count,
        "current_total_iterations": int(current.get("total_iterations", 0) or 0),
        "current_pass_rate": float(current.get("pass_rate", 0.0) or 0.0),
        "baseline_total_iterations": int((baseline or {}).get("total_iterations", 0) or 0),
        "baseline_pass_rate": float((baseline or {}).get("pass_rate", 0.0) or 0.0)
        if baseline is not None
        else None,
        "suites": rows,
    }


def _to_markdown(trend: dict[str, object]) -> str:
    lines = [
        "# Nightly Flaky Trend",
        "",
        f"- overall_trend: {trend.get('overall_trend', 'stable')}",
        f"- improved_suites: {trend.get('improved_suites', 0)}",
        f"- regressed_suites: {trend.get('regressed_suites', 0)}",
        f"- stable_suites: {trend.get('stable_suites', 0)}",
        f"- baseline_available: {trend.get('baseline_available', False)}",
        f"- baseline_status: {trend.get('baseline_status', 'unknown')}",
        f"- current_total_iterations: {trend.get('current_total_iterations', 0)}",
        f"- current_pass_rate: {trend.get('current_pass_rate', 0.0)}",
    ]
    baseline_note = str(trend.get("baseline_note", "")).strip()
    if baseline_note:
        lines.append(f"- baseline_note: {baseline_note}")
    if trend.get("baseline_available"):
        lines.append(f"- baseline_total_iterations: {trend.get('baseline_total_iterations', 0)}")
        lines.append(f"- baseline_pass_rate: {trend.get('baseline_pass_rate', 0.0)}")
    lines.append("")
    for row in trend.get("suites", []):
        if not isinstance(row, dict):
            continue
        lines.extend(
            [
                f"## {row.get('suite', '')}",
                f"- summary: {row.get('trend', 'unknown')}",
                f"- pass_rate_delta: {row.get('pass_rate_delta')}",
                f"- duration_mean_delta_seconds: {row.get('duration_mean_delta_seconds')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build flaky-watch trend report from current/baseline JSON.")
    parser.add_argument("--current", required=True, help="Current flaky-watch JSON report path.")
    parser.add_argument("--baseline", default="", help="Optional baseline flaky-watch JSON report path.")
    parser.add_argument("--output", required=True, help="Output trend JSON path.")
    parser.add_argument("--markdown-output", default="", help="Optional output markdown path.")
    parser.add_argument("--baseline-status", default="available", help="Baseline fetch status marker.")
    parser.add_argument("--baseline-note", default="", help="Optional baseline fetch note.")
    args = parser.parse_args()

    current = _load_json(args.current)
    baseline = _load_json(args.baseline) if args.baseline else None
    trend = build_trend(
        current=current,
        baseline=baseline,
        baseline_status=str(args.baseline_status or "unknown"),
        baseline_note=str(args.baseline_note or ""),
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(trend, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    if args.markdown_output:
        md = Path(args.markdown_output)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(_to_markdown(trend), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
