"""Sync routing benchmark scores from eval baseline comparison reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.services.routing_policy_service import RoutingPolicyService

# Eval scenario category → routing benchmark task key.
EVAL_CATEGORY_TO_TASK: dict[str, str] = {
    "coding": "coding",
    "cursor_parity": "coding",
    "model_benchmark": "coding",
    "humaneval": "coding",
    "mbpp": "coding",
    "local": "debug",
    "retrieval": "debug",
    "platform": "general",
    "web": "general",
}

DEFAULT_TASK = "general"


def category_to_task_type(category: str) -> str:
    return EVAL_CATEGORY_TO_TASK.get(category.strip().lower(), DEFAULT_TASK)


def compute_model_task_scores(
    rows: list[dict[str, object]],
    *,
    category_by_scenario_id: dict[str, str],
) -> dict[str, dict[str, float]]:
    """Aggregate pass-rate per (model, task_type) from benchmark rows."""
    buckets: dict[str, dict[str, list[int]]] = {}
    for row in rows:
        model = str(row.get("model", "")).strip()
        scenario_id = str(row.get("scenario_id", "")).strip()
        if not model or not scenario_id:
            continue
        category = category_by_scenario_id.get(scenario_id, DEFAULT_TASK)
        task = category_to_task_type(category)
        passed = 1 if str(row.get("status", "")) == "passed" else 0
        buckets.setdefault(model, {}).setdefault(task, []).append(passed)

    scores: dict[str, dict[str, float]] = {}
    for model, task_buckets in buckets.items():
        scores[model] = {}
        for task, values in task_buckets.items():
            scores[model][task] = round(sum(values) / len(values), 4)
    return scores


def load_latest_benchmark_report(report_file_path: str | Path) -> Optional[dict[str, object]]:
    path = Path(report_file_path)
    if not path.exists():
        return None
    latest: Optional[dict[str, object]] = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "benchmark_id" in payload and "rows" in payload:
            latest = payload
    return latest


class RoutingBenchmarkSyncService:
    def __init__(
        self,
        routing_policy: RoutingPolicyService,
        *,
        report_file_path: str = "./data/eval_reports.jsonl",
    ) -> None:
        self._routing_policy = routing_policy
        self._report_file_path = Path(report_file_path)

    def sync_from_report(
        self,
        report: dict[str, object],
        *,
        category_by_scenario_id: dict[str, str],
        blend_alpha: float = 0.3,
        persist: bool = True,
        dry_run: bool = False,
    ) -> dict[str, object]:
        rows = report.get("rows")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Benchmark report has no rows.")

        computed = compute_model_task_scores(
            [item for item in rows if isinstance(item, dict)],
            category_by_scenario_id=category_by_scenario_id,
        )
        if not computed:
            raise ValueError("No model scores could be computed from benchmark rows.")

        if dry_run:
            return {
                "dry_run": True,
                "benchmark_id": report.get("benchmark_id"),
                "computed_scores": computed,
                "updated_models": sorted(computed.keys()),
                "blend_alpha": blend_alpha,
            }

        summary = self._routing_policy.update_benchmark_scores(
            computed,
            blend_alpha=blend_alpha,
            persist=persist,
        )
        summary["benchmark_id"] = report.get("benchmark_id")
        summary["computed_scores"] = computed
        summary["dry_run"] = False
        summary["synced_at"] = datetime.now(timezone.utc).isoformat()
        return summary

    def sync_from_latest_report(
        self,
        *,
        category_by_scenario_id: dict[str, str],
        blend_alpha: float = 0.3,
        persist: bool = True,
        dry_run: bool = False,
    ) -> dict[str, object]:
        report = load_latest_benchmark_report(self._report_file_path)
        if report is None:
            raise ValueError(f"No benchmark report found in {self._report_file_path}")
        return self.sync_from_report(
            report,
            category_by_scenario_id=category_by_scenario_id,
            blend_alpha=blend_alpha,
            persist=persist,
            dry_run=dry_run,
        )
