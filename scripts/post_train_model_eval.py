#!/usr/bin/env python3
"""Запуск model_llm benchmark-среза с указанной моделью (KPI до/после finetune)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.eval_standalone import build_standalone_eval_service, default_post_dpo_scenario_ids


def _normalize_model(raw: str) -> str:
    model = raw.strip()
    if not model:
        return model
    if ":" in model:
        return model
    return f"ollama:{model}"


def _parse_scenario_ids(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Model-bound LLM eval для finetune KPI")
    parser.add_argument("--model", required=True, help="ID модели, напр. ollama:termit-core-ft")
    default_ids = default_post_dpo_scenario_ids()
    parser.add_argument(
        "--scenario-ids",
        default=default_ids,
        help="ID сценариев через запятую (MB/KPI или полный post-DPO slice)",
    )
    parser.add_argument("--output", required=True, help="Путь JSON-отчёта")
    parser.add_argument("--persist-report", action="store_true", help="Сохранить отчёт в eval store")
    args = parser.parse_args()

    scenario_ids = _parse_scenario_ids(args.scenario_ids)
    if not scenario_ids:
        print("Не заданы scenario ids.", file=sys.stderr)
        return 2

    model = _normalize_model(args.model)
    service = build_standalone_eval_service(root_path=str(ROOT))
    report = service.run_scenario_ids(
        scenario_ids,
        persist_report=args.persist_report,
        category_filter="model_kpi",
        model=model,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "pass_rate": report["pass_rate"], "total": report["total"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
