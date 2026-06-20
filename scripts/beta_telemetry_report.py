#!/usr/bin/env python3
"""Отчёт beta telemetry и product KPI gates (staging/local)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fetch_json(url: str, api_key: str = "") -> dict[str, Any] | None:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw.strip() else {}
            return payload if isinstance(payload, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def _load_beta_meta(root: Path, base_url: str) -> dict[str, Any] | None:
    """Локальный dev meta только для local API (:8765), не для hosted staging."""
    flag = os.getenv("TERMIT_BETA_USE_LOCAL_META", "auto").lower()
    if flag in {"0", "false", "no"}:
        return None
    host = base_url.rstrip("/").split("://", 1)[-1]
    is_local_dev = host in {"127.0.0.1:8765", "localhost:8765"}
    if flag == "auto" and not is_local_dev:
        return None
    path = root / "data" / "beta_cohort_meta.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def evaluate_beta_staging(
    *,
    beta: dict[str, Any],
    gates: dict[str, Any] | None,
    min_cohort_d30: int,
    gate_mode: str = "d30",
    min_tracked: int = 5,
    min_active_7d: int = 3,
    require_product_gates: bool = True,
) -> dict[str, Any]:
    """Сводка beta/staging gate для CLI и shell."""
    cohort = int(beta.get("cohort_size_d30", 0) or 0)
    tracked = int(beta.get("tracked_actors", 0) or 0)
    active_7d = int(beta.get("active_users_7d", 0) or 0)
    d30 = beta.get("d30_retention_rate")
    gates_passed = bool((gates or {}).get("overall_passed")) if gates else False
    failed_gates = [
        g.get("gate_id")
        for g in (gates or {}).get("gates", [])
        if isinstance(g, dict) and not g.get("passed")
    ]

    mode = gate_mode.strip().lower()
    if mode == "real":
        cohort_ok = tracked >= min_tracked and active_7d >= min_active_7d
        retention_ok = True
        staging_ok = cohort_ok and (gates_passed if require_product_gates else True)
    else:
        cohort_ok = cohort >= min_cohort_d30
        retention_ok = True
        if cohort >= min_cohort_d30 and isinstance(d30, (int, float)):
            retention_ok = float(d30) >= float(beta.get("target_d30_retention", 0.35) or 0.35)
        staging_ok = cohort_ok and (gates_passed if require_product_gates else True)

    return {
        "gate_mode": mode,
        "require_product_gates": require_product_gates,
        "cohort_size_d30": cohort,
        "d30_retention_rate": d30,
        "tracked_actors": tracked,
        "active_users_7d": active_7d,
        "min_cohort_d30": min_cohort_d30,
        "min_tracked": min_tracked,
        "min_active_7d": min_active_7d,
        "cohort_ok": cohort_ok,
        "retention_ok": retention_ok,
        "product_gates_passed": gates_passed,
        "failed_gates": failed_gates,
        "staging_ok": staging_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Beta telemetry report + staging gate")
    parser.add_argument(
        "--base-url",
        default=os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765"),
    )
    parser.add_argument("--api-key", default=os.getenv("TERMIT_API_KEY", ""))
    parser.add_argument(
        "--min-cohort-d30",
        type=int,
        default=int(os.getenv("TERMIT_BETA_MIN_COHORT_D30", "5")),
    )
    parser.add_argument(
        "--gate-mode",
        default=os.getenv("TERMIT_BETA_GATE_MODE", "d30"),
        choices=("d30", "real"),
        help="d30=cohort_size_d30; real=tracked_actors для свежего staging",
    )
    parser.add_argument(
        "--min-tracked",
        type=int,
        default=int(os.getenv("TERMIT_BETA_MIN_TRACKED", "5")),
    )
    parser.add_argument(
        "--min-active-7d",
        type=int,
        default=int(os.getenv("TERMIT_BETA_MIN_ACTIVE_7D", "3")),
    )
    parser.add_argument(
        "--require-product-gates",
        default=os.getenv("TERMIT_BETA_REQUIRE_PRODUCT_GATES", "true"),
        choices=("true", "false"),
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    beta = _fetch_json(f"{base}/api/ops/beta-metrics", args.api_key) or {}
    gates = _fetch_json(f"{base}/api/desktop/kpi-gates", args.api_key)
    meta = _load_beta_meta(ROOT, base)

    summary = evaluate_beta_staging(
        beta=beta,
        gates=gates,
        min_cohort_d30=max(1, args.min_cohort_d30),
        gate_mode=args.gate_mode,
        min_tracked=max(1, args.min_tracked),
        min_active_7d=max(1, args.min_active_7d),
        require_product_gates=args.require_product_gates.lower() == "true",
    )
    if meta and meta.get("dev_only"):
        summary["beta_dev_seed"] = True
    summary["beta_metrics"] = beta
    summary["desktop_kpi_gates"] = gates

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.output:
        Path(args.output).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.strict and not summary.get("staging_ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
