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
        reference_model: str = "openai_compat:deepseek-ai/DeepSeek-V4-Pro",
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

    def list_recent_benchmarks(self, *, limit: int = 6) -> list[dict[str, object]]:
        cap = max(1, min(limit, 52))
        if not self._report_file_path.exists():
            return []
        rows: list[dict[str, object]] = []
        for line in self._report_file_path.read_text(encoding="utf-8").splitlines():
            payload_raw = line.strip()
            if not payload_raw:
                continue
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(payload, dict)
                and payload.get("benchmark_id")
                and isinstance(payload.get("rows"), list)
            ):
                rows.append(payload)
        return rows[-cap:]

    def build_capability_review(self, *, limit: int = 6) -> dict[str, object]:
        reports = self.list_recent_benchmarks(limit=limit)
        if not reports:
            return {
                "total_reports": 0,
                "window": max(1, min(limit, 52)),
                "latest_benchmark_id": None,
                "latest_timestamp": None,
                "trend_direction": "no_data",
                "mean_pass_gap": 0.0,
                "mean_quality_gap": 0.0,
                "termit_win_rate": 0.0,
                "reports": [],
                "notes": ["No benchmark history found. Run /api/eval/benchmark/baselines first."],
            }
        points: list[dict[str, object]] = []
        pass_gaps: list[float] = []
        quality_gaps: list[float] = []
        wins = 0
        for item in reports:
            termit_pass = float(item.get("termit_pass_rate", 0.0) or 0.0)
            reference_pass = float(item.get("reference_pass_rate", 0.0) or 0.0)
            termit_quality = float(item.get("termit_quality_mean", 0.0) or 0.0)
            reference_quality = float(item.get("reference_quality_mean", 0.0) or 0.0)
            pass_gap = round(termit_pass - reference_pass, 4)
            quality_gap = round(termit_quality - reference_quality, 4)
            if pass_gap > 0:
                wins += 1
            pass_gaps.append(pass_gap)
            quality_gaps.append(quality_gap)
            points.append(
                {
                    "benchmark_id": str(item.get("benchmark_id", "")),
                    "timestamp": str(item.get("timestamp", "")),
                    "termit_pass_rate": termit_pass,
                    "reference_pass_rate": reference_pass,
                    "pass_rate_gap": pass_gap,
                    "termit_quality_mean": termit_quality,
                    "reference_quality_mean": reference_quality,
                    "quality_gap": quality_gap,
                }
            )

        trend_direction = "flat"
        if len(pass_gaps) >= 2:
            if pass_gaps[-1] > pass_gaps[0]:
                trend_direction = "improving"
            elif pass_gaps[-1] < pass_gaps[0]:
                trend_direction = "regressing"

        return {
            "total_reports": len(points),
            "window": max(1, min(limit, 52)),
            "latest_benchmark_id": str(points[-1]["benchmark_id"]) if points else None,
            "latest_timestamp": str(points[-1]["timestamp"]) if points else None,
            "trend_direction": trend_direction,
            "mean_pass_gap": round(sum(pass_gaps) / len(pass_gaps), 4),
            "mean_quality_gap": round(sum(quality_gaps) / len(quality_gaps), 4),
            "termit_win_rate": round(wins / len(pass_gaps), 4) if pass_gaps else 0.0,
            "reports": points,
            "notes": [
                "pass_rate_gap > 0 means Termit beats reference by task success.",
                "quality_gap > 0 means Termit output quality beats reference.",
            ],
        }

    def build_capability_regression(
        self,
        *,
        baseline: dict[str, object],
        limit: int = 6,
        max_pass_gap_drop: float = 0.05,
        max_quality_gap_drop: float = 0.05,
        max_win_rate_drop: float = 0.10,
    ) -> dict[str, object]:
        current = self.build_capability_review(limit=limit)

        baseline_pass_gap = float(baseline.get("mean_pass_gap", 0.0) or 0.0)
        current_pass_gap = float(current.get("mean_pass_gap", 0.0) or 0.0)
        baseline_quality_gap = float(baseline.get("mean_quality_gap", 0.0) or 0.0)
        current_quality_gap = float(current.get("mean_quality_gap", 0.0) or 0.0)
        baseline_win_rate = float(baseline.get("termit_win_rate", 0.0) or 0.0)
        current_win_rate = float(current.get("termit_win_rate", 0.0) or 0.0)

        pass_gap_delta = round(current_pass_gap - baseline_pass_gap, 4)
        quality_gap_delta = round(current_quality_gap - baseline_quality_gap, 4)
        win_rate_delta = round(current_win_rate - baseline_win_rate, 4)

        baseline_reports = int(baseline.get("total_reports", 0) or 0)
        current_reports = int(current.get("total_reports", 0) or 0)
        min_reports = max(1, baseline_reports)
        trend = str(current.get("trend_direction", "no_data")).strip().lower()
        allowed_trends = ["flat", "improving"]

        gate_passed = (
            current_reports >= min_reports
            and pass_gap_delta + 1e-9 >= -abs(max_pass_gap_drop)
            and quality_gap_delta + 1e-9 >= -abs(max_quality_gap_drop)
            and win_rate_delta + 1e-9 >= -abs(max_win_rate_drop)
            and trend in {"flat", "improving"}
        )

        notes: list[str] = []
        if current_reports < min_reports:
            notes.append(f"Not enough reports: {current_reports} < {min_reports}.")
        if pass_gap_delta + 1e-9 < -abs(max_pass_gap_drop):
            notes.append(
                f"mean_pass_gap regression {pass_gap_delta:.4f} exceeds allowed drop {max_pass_gap_drop:.4f}."
            )
        if quality_gap_delta + 1e-9 < -abs(max_quality_gap_drop):
            notes.append(
                "mean_quality_gap regression "
                f"{quality_gap_delta:.4f} exceeds allowed drop {max_quality_gap_drop:.4f}."
            )
        if win_rate_delta + 1e-9 < -abs(max_win_rate_drop):
            notes.append(
                f"termit_win_rate regression {win_rate_delta:.4f} exceeds allowed drop {max_win_rate_drop:.4f}."
            )
        if trend not in {"flat", "improving"}:
            notes.append(f"trend_direction '{trend}' is outside allowed values {allowed_trends}.")
        if not notes:
            notes.append("Capability regression gate passed.")

        return {
            "baseline_total_reports": baseline_reports,
            "current_total_reports": current_reports,
            "required_min_reports": min_reports,
            "baseline_mean_pass_gap": baseline_pass_gap,
            "current_mean_pass_gap": current_pass_gap,
            "mean_pass_gap_delta": pass_gap_delta,
            "max_pass_gap_drop": max(0.0, float(max_pass_gap_drop)),
            "baseline_mean_quality_gap": baseline_quality_gap,
            "current_mean_quality_gap": current_quality_gap,
            "mean_quality_gap_delta": quality_gap_delta,
            "max_quality_gap_drop": max(0.0, float(max_quality_gap_drop)),
            "baseline_termit_win_rate": baseline_win_rate,
            "current_termit_win_rate": current_win_rate,
            "termit_win_rate_delta": win_rate_delta,
            "max_win_rate_drop": max(0.0, float(max_win_rate_drop)),
            "current_trend_direction": trend,
            "allowed_trend_directions": allowed_trends,
            "gate_passed": gate_passed,
            "notes": notes,
        }

    def refresh_capability_baseline(
        self,
        *,
        baseline_file_path: str,
        limit: int = 12,
    ) -> dict[str, object]:
        review = self.build_capability_review(limit=max(1, min(limit, 52)))
        payload = {
            "total_reports": int(review.get("total_reports", 0) or 0),
            "mean_pass_gap": float(review.get("mean_pass_gap", 0.0) or 0.0),
            "mean_quality_gap": float(review.get("mean_quality_gap", 0.0) or 0.0),
            "termit_win_rate": float(review.get("termit_win_rate", 0.0) or 0.0),
            "trend_direction": str(review.get("trend_direction", "no_data")),
            "latest_benchmark_id": review.get("latest_benchmark_id"),
            "latest_timestamp": review.get("latest_timestamp"),
            "window": int(review.get("window", 0) or 0),
            "note": "Auto-refreshed from capability review history.",
        }
        target = Path(baseline_file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return payload
