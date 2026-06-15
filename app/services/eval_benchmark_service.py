"""Baseline comparison: Termit runtime vs cloud reference models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class BenchmarkRow:
    scenario_id: str
    system: str
    model: str
    status: str
    pass_rate_component: int
    quality_score: float
    duration_ms: int
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "system": self.system,
            "model": self.model,
            "status": self.status,
            "task_success": self.pass_rate_component,
            "quality_score": self.quality_score,
            "duration_ms": self.duration_ms,
            "detail": self.detail,
        }


class EvalBenchmarkService:
    def __init__(
        self,
        *,
        report_file_path: str = "./data/eval_reports.jsonl",
        termit_model: str = "ollama:termit-core-ft",
        reference_model: str = "openai_compat:deepseek-ai/DeepSeek-V3",
        scenario_runner: Optional[Callable[[str, str], dict[str, object]]] = None,
        quality_judge: Optional[Callable[[dict[str, object]], float]] = None,
    ) -> None:
        self._report_file_path = Path(report_file_path)
        self._termit_model = termit_model.strip()
        self._reference_model = reference_model.strip()
        self._scenario_runner = scenario_runner
        self._quality_judge = quality_judge
        self._report_file_path.parent.mkdir(parents=True, exist_ok=True)

    def compare_on_scenarios(
        self,
        scenario_ids: list[str],
        *,
        persist: bool = True,
    ) -> dict[str, object]:
        if self._scenario_runner is None:
            raise ValueError("Benchmark runner is not configured.")

        rows: list[BenchmarkRow] = []
        for scenario_id in scenario_ids:
            termit_result = self._scenario_runner(scenario_id, self._termit_model)
            rows.append(self._to_row("termit", self._termit_model, termit_result))
            ref_result = self._scenario_runner(scenario_id, self._reference_model)
            rows.append(self._to_row("reference", self._reference_model, ref_result))

        termit_pass = sum(1 for row in rows if row.system == "termit" and row.status == "passed")
        ref_pass = sum(1 for row in rows if row.system == "reference" and row.status == "passed")
        termit_scores = [row.quality_score for row in rows if row.system == "termit"]
        ref_scores = [row.quality_score for row in rows if row.system == "reference"]
        total_each = max(1, len(scenario_ids))

        report = {
            "benchmark_id": f"bench_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario_ids": scenario_ids,
            "termit_model": self._termit_model,
            "reference_model": self._reference_model,
            "termit_pass_rate": round(termit_pass / total_each, 4),
            "reference_pass_rate": round(ref_pass / total_each, 4),
            "termit_quality_mean": round(sum(termit_scores) / len(termit_scores), 3)
            if termit_scores
            else 0.0,
            "reference_quality_mean": round(sum(ref_scores) / len(ref_scores), 3)
            if ref_scores
            else 0.0,
            "rows": [row.as_dict() for row in rows],
        }
        if persist:
            with self._report_file_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(report, ensure_ascii=False) + "\n")
        return report

    def _to_row(self, system: str, model: str, result: dict[str, object]) -> BenchmarkRow:
        status = str(result.get("status", "failed"))
        quality = float(result.get("quality_score", 0.0) or 0.0)
        if self._quality_judge is not None and quality <= 0:
            quality = float(self._quality_judge(result))
        return BenchmarkRow(
            scenario_id=str(result.get("scenario_id", "")),
            system=system,
            model=model,
            status=status,
            pass_rate_component=1 if status == "passed" else 0,
            quality_score=quality,
            duration_ms=int(result.get("duration_ms", 0) or 0),
            detail=str(result.get("message", ""))[:300],
        )
