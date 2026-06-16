#!/usr/bin/env python3
"""Promote current eval report to baseline when regression gate passes."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_REGRESSION_PATH = ROOT / "scripts" / "eval_regression_report.py"
_spec = importlib.util.spec_from_file_location("eval_regression_report", _REGRESSION_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load {_REGRESSION_PATH}")
_regression = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_regression)
compare_eval_reports = _regression.compare_eval_reports
_load_report = _regression._load_report


def promote_baseline(
    *,
    baseline_path: Path,
    current_path: Path,
    max_pass_rate_drop: float,
    min_improvement: float,
    dry_run: bool,
) -> tuple[bool, dict[str, object]]:
    baseline = _load_report(baseline_path)
    current = _load_report(current_path)
    ok, summary = compare_eval_reports(
        baseline=baseline,
        current=current,
        max_pass_rate_drop=max_pass_rate_drop,
    )
    delta = float(summary.get("pass_rate_delta", 0.0) or 0.0)
    summary["min_improvement_required"] = min_improvement
    summary["promoted"] = False

    if not ok:
        summary["reason"] = "Regression gate failed; baseline unchanged."
        return False, summary

    if delta + 1e-9 < min_improvement:
        summary["reason"] = (
            f"Gate passed but improvement {delta:+.2%} below min {min_improvement:.2%}; baseline unchanged."
        )
        return True, summary

    if dry_run:
        summary["promoted"] = True
        summary["reason"] = "Dry run: would promote current report to baseline."
        return True, summary

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if baseline_path.exists():
        backup = baseline_path.with_suffix(f".json.bak.{stamp}")
        shutil.copy2(baseline_path, backup)
        summary["backup_path"] = str(backup)

    promoted = dict(current)
    promoted["promoted_at"] = datetime.now(timezone.utc).isoformat()
    promoted["previous_baseline_pass_rate"] = float(summary.get("baseline_pass_rate", 0.0) or 0.0)
    promoted["pass_rate_delta"] = delta
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(promoted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary["promoted"] = True
    summary["reason"] = f"Baseline updated (delta {delta:+.2%})."
    summary["baseline_path"] = str(baseline_path)
    return True, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote eval report to baseline after green gate")
    parser.add_argument("--baseline", required=True, help="Baseline JSON path to update")
    parser.add_argument("--current", required=True, help="Current eval report JSON path")
    parser.add_argument("--max-pass-rate-drop", type=float, default=0.05)
    parser.add_argument(
        "--min-improvement",
        type=float,
        default=0.0,
        help="Minimum pass_rate improvement vs baseline to promote (0 = any green gate)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    ok, summary = promote_baseline(
        baseline_path=Path(args.baseline),
        current_path=Path(args.current),
        max_pass_rate_drop=max(0.0, float(args.max_pass_rate_drop)),
        min_improvement=float(args.min_improvement),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.output:
        Path(args.output).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not ok:
        return 1
    if not summary.get("promoted") and not args.dry_run:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
