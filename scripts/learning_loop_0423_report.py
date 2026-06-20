#!/usr/bin/env python3
"""Сборка артефакта learning loop 0.4.23 (probes, DPO, post-eval, KPI, cloud)."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def default_post_dpo_scenario_ids() -> str:
    """ID сценариев для post-DPO eval: MB1–MB3 + HumanEval + MBPP."""
    override = os.getenv("TERMIT_EVAL_POST_DPO_IDS", "").strip()
    if override:
        return override
    if os.getenv("TERMIT_EVAL_POST_DPO_FULL", "true").lower() in {"1", "true", "yes"}:
        return "MB1,MB2,MB3,HE1,HE2,MBPP1,MBPP2"
    return os.getenv("TERMIT_EVAL_MODEL_KPI_IDS", "MB1,MB2,MB3")


def pass_rate_from_report(path: Path) -> Optional[float]:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if "pass_rate" in payload:
        return float(payload["pass_rate"])
    results = payload.get("results")
    if isinstance(results, list) and results:
        passed = sum(1 for row in results if row.get("passed") or row.get("status") == "passed")
        return passed / len(results)
    return None


def build_learning_loop_report(
    *,
    gpu: dict[str, Any],
    cloud: dict[str, Any],
    dpo_train: dict[str, Any] | None,
    baseline_path: Path,
    post_dpo_path: Path,
    kpi_path: Path,
    scenario_ids: str,
    model: str,
    cloud_benchmark_ran: bool,
    remote_gpu: bool = False,
) -> dict[str, Any]:
    """Собрать JSON-отчёт learning loop 0.4.23."""
    kpi: dict[str, Any] | None = None
    if kpi_path.is_file():
        try:
            raw = json.loads(kpi_path.read_text(encoding="utf-8"))
            kpi = raw if isinstance(raw, dict) else None
        except (json.JSONDecodeError, OSError):
            kpi = None

    dpo_status = str((dpo_train or {}).get("status") or "skipped")
    dpo_detail = str((dpo_train or {}).get("detail") or "")
    dpo_real = bool(gpu.get("gpu_available")) and "dry-run" not in dpo_detail.lower()
    if remote_gpu and dpo_status == "completed":
        dpo_real = True

    baseline_rate = pass_rate_from_report(baseline_path)
    post_rate = pass_rate_from_report(post_dpo_path)

    model_ids = {"MB1", "MB2", "MB3", "MT1", "MT2"}
    id_list = [item.strip() for item in scenario_ids.split(",") if item.strip()]
    kpi_measurable = dpo_real and bool(model_ids.intersection(id_list))

    return {
        "phase": "0.4.23",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "scenario_ids": id_list,
        "gpu": gpu,
        "cloud_benchmark_probe": cloud,
        "cloud_benchmark_ran": cloud_benchmark_ran,
        "remote_gpu": remote_gpu,
        "dpo_train": dpo_train,
        "dpo_real_train": dpo_real,
        "baseline_report": str(baseline_path),
        "baseline_pass_rate": baseline_rate,
        "post_dpo_report": str(post_dpo_path),
        "post_dpo_pass_rate": post_rate,
        "eval_kpi": kpi,
        "kpi_passed": bool(kpi.get("kpi_passed")) if kpi else False,
        "kpi_measurable": kpi_measurable,
        "dev_kpi_seed": bool(kpi.get("dev_only")) if kpi else False,
        "paths": {
            "baseline": str(baseline_path),
            "post_dpo": str(post_dpo_path),
            "kpi": str(kpi_path),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Learning loop 0.4.23 artifact builder")
    parser.add_argument("--gpu-json", default="", help="JSON gpu_probe")
    parser.add_argument("--cloud-json", default="", help="JSON cloud_benchmark_probe")
    parser.add_argument("--dpo-json", default="", help="JSON DPO train result")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--post-dpo", required=True)
    parser.add_argument("--kpi", required=True)
    parser.add_argument("--model", default=os.getenv("TERMIT_FINETUNE_OUTPUT_MODEL", "termit-core-ft"))
    parser.add_argument(
        "--scenario-ids",
        default=default_post_dpo_scenario_ids(),
    )
    parser.add_argument("--cloud-ran", action="store_true")
    parser.add_argument("--remote-gpu", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    gpu = json.loads(args.gpu_json) if args.gpu_json.strip() else {"gpu_available": False}
    cloud = json.loads(args.cloud_json) if args.cloud_json.strip() else {"ready": False}
    dpo_train = json.loads(args.dpo_json) if args.dpo_json.strip() else None

    report = build_learning_loop_report(
        gpu=gpu,
        cloud=cloud,
        dpo_train=dpo_train,
        baseline_path=Path(args.baseline),
        post_dpo_path=Path(args.post_dpo),
        kpi_path=Path(args.kpi),
        scenario_ids=args.scenario_ids,
        model=args.model,
        cloud_benchmark_ran=args.cloud_ran,
        remote_gpu=args.remote_gpu,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
