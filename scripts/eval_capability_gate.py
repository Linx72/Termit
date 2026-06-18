#!/usr/bin/env python3
"""Validate benchmark capability-review report against baseline thresholds."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _as_float(payload: dict[str, object], key: str) -> float:
    return float(payload.get(key, 0.0) or 0.0)


def _as_int(payload: dict[str, object], key: str) -> int:
    return int(payload.get(key, 0) or 0)


def _normalize_allowed_trends(raw: str) -> set[str]:
    items = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return items or {"flat", "improving"}


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

    report = json.load(sys.stdin)

    min_reports = int(os.getenv("TERMIT_CAP_MIN_REPORTS", "2"))
    min_pass_gap = float(os.getenv("TERMIT_CAP_MIN_MEAN_PASS_GAP", "-0.05"))
    min_quality_gap = float(os.getenv("TERMIT_CAP_MIN_MEAN_QUALITY_GAP", "-0.10"))
    min_win_rate = float(os.getenv("TERMIT_CAP_MIN_WIN_RATE", "0.40"))
    allowed_trends = _normalize_allowed_trends(
        os.getenv("TERMIT_CAP_ALLOWED_TRENDS", "flat,improving")
    )

    total_reports = _as_int(report, "total_reports")
    mean_pass_gap = _as_float(report, "mean_pass_gap")
    mean_quality_gap = _as_float(report, "mean_quality_gap")
    termit_win_rate = _as_float(report, "termit_win_rate")
    trend_direction = str(report.get("trend_direction", "no_data")).strip().lower()

    if total_reports < min_reports:
        print(f"Capability gate failed: total_reports={total_reports} < required {min_reports}.")
        return 1
    if mean_pass_gap + 1e-9 < min_pass_gap:
        print(
            f"Capability gate failed: mean_pass_gap {mean_pass_gap:.4f} "
            f"< {min_pass_gap:.4f}."
        )
        return 1
    if mean_quality_gap + 1e-9 < min_quality_gap:
        print(
            f"Capability gate failed: mean_quality_gap {mean_quality_gap:.4f} "
            f"< {min_quality_gap:.4f}."
        )
        return 1
    if termit_win_rate + 1e-9 < min_win_rate:
        print(
            f"Capability gate failed: termit_win_rate {termit_win_rate:.4f} "
            f"< {min_win_rate:.4f}."
        )
        return 1
    if trend_direction not in allowed_trends:
        options = ",".join(sorted(allowed_trends))
        print(
            "Capability gate failed: trend_direction "
            f"{trend_direction!r} not in allowed [{options}]."
        )
        return 1

    print(
        "Capability gate passed: "
        f"total_reports={total_reports}, "
        f"mean_pass_gap={mean_pass_gap:.4f}, "
        f"mean_quality_gap={mean_quality_gap:.4f}, "
        f"termit_win_rate={termit_win_rate:.4f}, "
        f"trend_direction={trend_direction}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
