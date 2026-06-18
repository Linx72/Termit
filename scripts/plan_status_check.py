#!/usr/bin/env python3
"""Статус плана фазы 5: продуктовые KPI, learning loop, блокеры cloud/GPU."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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


def _run_probe(script: str) -> dict[str, Any]:
    python_bin = ROOT / ".venv/bin/python"
    if not python_bin.exists():
        python_bin = Path(sys.executable)
    proc = subprocess.run(
        [str(python_bin), str(ROOT / "scripts" / script)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        return {"error": proc.stderr.strip() or f"exit {proc.returncode}"}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw": proc.stdout.strip()}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def collect_plan_status() -> dict[str, Any]:
    base_url = os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    api_key = os.getenv("TERMIT_API_KEY", "")
    data_dir = ROOT / "data"

    health = _curl_json(f"{base_url}/health", api_key)
    kpi_gates = _curl_json(f"{base_url}/api/desktop/kpi-gates", api_key)
    beta = _curl_json(f"{base_url}/api/ops/beta-metrics", api_key)
    automation = _curl_json(f"{base_url}/api/ops/automation", api_key)
    finetune_kpi = _load_json(data_dir / "eval_kpi_last.json")
    gpu = _run_probe("gpu_probe.py")
    cloud = _run_probe("cloud_benchmark_probe.py")

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if health is None:
        blockers.append({"id": "api_down", "message": f"Termit API недоступен: {base_url}"})

    if not gpu.get("gpu_available"):
        warnings.append(
            {
                "id": "no_gpu",
                "message": "Нет NVIDIA GPU — DPO/HF train только dry-run; KPI +5% маловероятен.",
            }
        )

    if not cloud.get("ready"):
        warnings.append(
            {
                "id": "cloud_benchmark",
                "message": str(
                    cloud.get("hint") or cloud.get("reason") or "Cloud benchmark не готов."
                ),
            }
        )

    if finetune_kpi is not None and not finetune_kpi.get("kpi_passed"):
        warnings.append(
            {
                "id": "finetune_kpi",
                "message": str(
                    finetune_kpi.get("reason") or "Finetune eval KPI не достигнут (цель +5%)."
                ),
            }
        )
    elif finetune_kpi is None:
        warnings.append(
            {
                "id": "finetune_kpi",
                "message": "Нет eval_kpi_last.json — запустите training_loop_full.sh.",
            }
        )

    product_gates_passed = bool(kpi_gates.get("overall_passed")) if kpi_gates else False
    if kpi_gates and not product_gates_passed:
        failed = [
            g.get("gate_id")
            for g in kpi_gates.get("gates", [])
            if isinstance(g, dict) and not g.get("passed")
        ]
        warnings.append(
            {
                "id": "product_kpi",
                "message": f"Desktop KPI gates не пройдены (failed: {', '.join(map(str, failed)) or 'unknown'}).",
            }
        )

    d30 = beta.get("d30_retention") if isinstance(beta, dict) else None
    cohort = int(beta.get("cohort_size", 0) or 0) if isinstance(beta, dict) else 0
    if cohort < 5:
        warnings.append(
            {
                "id": "beta_cohort",
                "message": f"Beta-когорта слишком мала ({cohort}) для D30 retention (нужно ≥5).",
            }
        )

    infra_ok = health is not None and not any(b["id"] == "api_down" for b in blockers)
    plan_code_complete = True  # фазы 0–4 закрыты в PROJECT_TASK_PROMPT_RU.md

    return {
        "phase": "5_production_kpi",
        "plan_code_complete": plan_code_complete,
        "infra_ok": infra_ok,
        "automatic_mode_enabled": bool(automation.get("automatic_mode_enabled")) if automation else None,
        "gpu": gpu,
        "cloud_benchmark": cloud,
        "finetune_eval_kpi": finetune_kpi,
        "desktop_kpi_gates": kpi_gates,
        "beta_metrics": beta,
        "d30_retention": d30,
        "blockers": blockers,
        "warnings": warnings,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }


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
        print(f"  БЛОКЕР:  [{item.get('id')}] {item.get('message')}")
    for item in payload.get("warnings") or []:
        print(f"  WARN:    [{item.get('id')}] {item.get('message')}")


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
