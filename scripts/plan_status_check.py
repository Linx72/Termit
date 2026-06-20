#!/usr/bin/env python3
"""Статус плана фазы 5: продуктовые KPI, learning loop, блокеры cloud/GPU."""

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


def _curl_json(url: str, api_key: str = "") -> dict[str, Any] | None:
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def collect_plan_status() -> dict[str, Any]:
    base_url = os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    api_key = os.getenv("TERMIT_API_KEY", "")
    prefer_local = os.getenv("TERMIT_PLAN_STATUS_LOCAL", "").lower() in {"1", "true", "yes"}

    health = _curl_json(f"{base_url}/health", api_key)

    if not prefer_local and health is not None:
        plan = _curl_json(f"{base_url}/api/ops/plan-status", api_key)
        if plan is not None:
            return plan

    from app.services.plan_status_service import build_plan_status_service

    # Локальный collect не требует живого API (CI unittest, do_all_plan offline).
    external_ok = True if prefer_local else health is not None
    return build_plan_status_service().collect(external_api_ok=external_ok)


def print_summary(payload: dict[str, Any]) -> None:
    print("== Статус плана (фаза 5) ==")
    print(f"  Infra OK:           {payload.get('infra_ok')}")
    print(f"  Код плана (0-4):    {payload.get('plan_code_complete')}")
    print(f"  Автоматизация:      {payload.get('automatic_mode_enabled')}")
    kpi = payload.get("finetune_eval_kpi") or {}
    if kpi:
        print(f"  Finetune KPI:       kpi_passed={kpi.get('kpi_passed')} delta={kpi.get('delta')}")
    gates = payload.get("desktop_kpi_gates") or {}
    if gates:
        print(f"  Product KPI gates:  overall_passed={gates.get('overall_passed')}")
    for item in payload.get("blockers") or []:
        msg_item = item if isinstance(item, dict) else {"id": "", "message": str(item)}
        print(f"  БЛОКЕР:  [{msg_item.get('id')}] {msg_item.get('message')}")
    for item in payload.get("warnings") or []:
        msg_item = item if isinstance(item, dict) else {"id": "", "message": str(item)}
        print(f"  WARN:    [{msg_item.get('id')}] {msg_item.get('message')}")
    for item in payload.get("relaxed_env_warnings") or []:
        msg_item = item if isinstance(item, dict) else {"id": "", "message": str(item)}
        print(f"  ENV:     [{msg_item.get('id')}] {msg_item.get('message')}")
    if payload.get("relax_env_warnings_enabled"):
        print(f"  overall_ok:         {payload.get('overall_ok')} (relax env warnings)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Статус плана Termit (фаза 5)")
    parser.add_argument("--output", default="", help="Путь для JSON-отчёта")
    parser.add_argument("--summary-only", action="store_true", help="Только краткая сводка")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 при blockers или предупреждениях finetune/product KPI",
    )
    args = parser.parse_args()

    payload = collect_plan_status()
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not args.summary_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    print_summary(payload)

    if args.strict:
        if payload.get("blocker_count", 0) > 0:
            return 1
        if payload.get("warning_count", 0) > 0:
            return 1
    elif payload.get("blocker_count", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
