#!/usr/bin/env python3
"""Fail nightly when flaky trend indicates regression on critical suites."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

RUNBOOK_HINT = "See docs/NIGHTLY_FLAKY_GATE_RUNBOOK_RU.md."


def _parse_iso_timestamp(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_active_overrides(overrides_payload: dict[str, object], *, now_utc: datetime) -> dict[str, str]:
    rows = overrides_payload.get("overrides", [])
    if not isinstance(rows, list):
        return {}
    active: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        suite = str(row.get("suite", "")).strip()
        reason = str(row.get("reason", "")).strip() or "temporary override"
        expires_at = str(row.get("expires_at", "")).strip()
        if not suite or not expires_at:
            continue
        expires_dt = _parse_iso_timestamp(expires_at)
        if expires_dt is None:
            continue
        if expires_dt >= now_utc:
            active[suite] = reason
    return active


def evaluate_gate(
    trend: dict[str, object],
    *,
    critical_suites: set[str],
    fail_on_any_regression: bool,
    override_reasons: dict[str, str] | None = None,
) -> tuple[bool, str]:
    def _with_runbook_hint(message: str) -> str:
        return f"{message} {RUNBOOK_HINT}"

    def _is_negative_delta(value: object) -> bool:
        return isinstance(value, (float, int)) and not isinstance(value, bool) and float(value) < 0.0

    overrides = override_reasons or {}
    rows = [row for row in trend.get("suites", []) if isinstance(row, dict)]
    regressed_rows = [
        row
        for row in rows
        if (
            str(row.get("trend", "")).strip().lower() == "regressed"
            or _is_negative_delta(row.get("pass_rate_delta"))
        )
        and str(row.get("suite", "")).strip() not in overrides
    ]
    if fail_on_any_regression and regressed_rows:
        suites = ", ".join(sorted(str(row.get("suite", "")) for row in regressed_rows))
        return False, _with_runbook_hint(f"Flaky trend gate failed: regressed suites detected: {suites}")

    for row in rows:
        suite = str(row.get("suite", "")).strip()
        if suite in overrides:
            continue
        if suite not in critical_suites:
            continue
        pass_delta = row.get("pass_rate_delta")
        if isinstance(pass_delta, bool):
            return False, _with_runbook_hint(
                f"Flaky trend gate failed: critical suite {suite} has invalid pass_rate_delta type"
            )
        if pass_delta is not None and not isinstance(pass_delta, (float, int)):
            return False, _with_runbook_hint(
                f"Flaky trend gate failed: critical suite {suite} has invalid pass_rate_delta type"
            )
        if isinstance(pass_delta, (float, int)) and float(pass_delta) < 0.0:
            return False, _with_runbook_hint(
                f"Flaky trend gate failed: critical suite {suite} pass_rate_delta={pass_delta}"
            )
        trend_label = str(row.get("trend", "")).strip().lower()
        if trend_label == "regressed":
            return False, _with_runbook_hint(
                f"Flaky trend gate failed: critical suite {suite} marked as regressed"
            )
    return True, "Flaky trend gate passed."


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate flaky trend regression gate.")
    parser.add_argument("--trend", required=True, help="Path to flaky trend JSON.")
    parser.add_argument(
        "--critical-suites",
        nargs="+",
        default=["tests.test_agents_api", "tests.test_platform_e2e"],
        help="Suites that must not regress.",
    )
    parser.add_argument(
        "--allow-noncritical-regressions",
        action="store_true",
        help="Do not fail when non-critical suites regress.",
    )
    parser.add_argument(
        "--overrides",
        default="",
        help=(
            "Optional JSON file with temporary suite overrides: "
            "{\"overrides\":[{\"suite\",\"expires_at\",\"reason\"}]}. "
            "Runbook: docs/NIGHTLY_FLAKY_GATE_RUNBOOK_RU.md"
        ),
    )
    parser.add_argument(
        "--now-utc",
        default="",
        help="Optional UTC timestamp for override evaluation (ISO8601).",
    )
    args = parser.parse_args()

    trend_path = Path(args.trend)
    try:
        payload = json.loads(trend_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid trend JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Invalid trend payload.")

    now_utc = datetime.now(timezone.utc)
    if args.now_utc:
        parsed = _parse_iso_timestamp(str(args.now_utc))
        if parsed is None:
            raise SystemExit("Invalid --now-utc timestamp.")
        now_utc = parsed

    overrides: dict[str, str] = {}
    overrides_notice = ""
    if args.overrides:
        overrides_path = Path(args.overrides)
        if overrides_path.is_file():
            try:
                raw = json.loads(overrides_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise SystemExit(f"Invalid overrides JSON: {exc}") from exc
            if not isinstance(raw, dict):
                raise SystemExit("Invalid overrides payload.")
            overrides = _load_active_overrides(raw, now_utc=now_utc)
        else:
            overrides_notice = f" Overrides ignored: path is not a file ({overrides_path})."

    ok, message = evaluate_gate(
        payload,
        critical_suites={item.strip() for item in args.critical_suites if item.strip()},
        fail_on_any_regression=not args.allow_noncritical_regressions,
        override_reasons=overrides,
    )
    if overrides:
        covered = ", ".join(f"{suite} ({reason})" for suite, reason in sorted(overrides.items()))
        message = f"{message} Active overrides: {covered}."
    if overrides_notice:
        message = f"{message}{overrides_notice}"
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
