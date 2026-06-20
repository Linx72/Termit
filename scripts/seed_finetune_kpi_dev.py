#!/usr/bin/env python3
"""Локальный dev-seed для finetune eval KPI (data/eval_kpi_last.json)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed finetune eval KPI for local plan status (dev only)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--output",
        default=os.getenv("TERMIT_EVAL_KPI_LAST", str(ROOT / "data" / "eval_kpi_last.json")),
    )
    args = parser.parse_args()

    if not args.force and os.getenv("TERMIT_FINETUNE_KPI_DEV_SEED", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        print(
            "Отказ: TERMIT_FINETUNE_KPI_DEV_SEED=true или --force (только local dev).",
            file=sys.stderr,
        )
        return 2

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dev_only": True,
        "baseline_pass_rate": 0.8,
        "current_pass_rate": 0.86,
        "min_improvement_required": 0.05,
        "delta": 0.06,
        "kpi_passed": True,
        "reason": "KPI met (dev seed): improvement +6.00% >= 5.00%.",
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"OK — finetune KPI seed → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
