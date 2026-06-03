"""KPI gate evaluation for desktop north-star targets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


class DesktopKpiGateService:
    def __init__(
        self,
        north_star_path: str,
        *,
        eval_dashboard_provider: Callable[[], dict[str, object]],
        agent_metrics_provider: Callable[[], dict[str, object]],
    ) -> None:
        self._path = Path(north_star_path)
        self._eval_dashboard_provider = eval_dashboard_provider
        self._agent_metrics_provider = agent_metrics_provider

    def _load_targets(self) -> dict[str, float]:
        if not self._path.is_file():
            return {}
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        targets = payload.get("kpi_targets", {})
        return {str(key): float(value) for key, value in targets.items()}

    def _load_journeys(self) -> list[dict[str, object]]:
        if not self._path.is_file():
            return []
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        return list(payload.get("journeys", []))

    def evaluate_gates(self) -> dict[str, object]:
        targets = self._load_targets()
        eval_dash = self._eval_dashboard_provider()
        agent_metrics = self._agent_metrics_provider()

        pass_rate = float(eval_dash.get("pass_rate", 0.0))
        tool_loop_completion = float(agent_metrics.get("tool_loop_completion_rate") or 0.0)
        tool_loop_success = float(agent_metrics.get("tool_loop_tool_success_rate") or 0.0)

        gates: list[dict[str, object]] = []

        def add_gate(
            gate_id: str,
            label: str,
            actual: float,
            target: float,
            *,
            higher_is_better: bool = True,
        ) -> None:
            if higher_is_better:
                passed = actual + 1e-9 >= target
            else:
                passed = actual <= target + 1e-9
            gates.append(
                {
                    "gate_id": gate_id,
                    "label": label,
                    "actual": round(actual, 4),
                    "target": target,
                    "passed": passed,
                    "higher_is_better": higher_is_better,
                }
            )

        add_gate(
            "eval_pass_rate",
            "Eval pass rate",
            pass_rate,
            targets.get("eval_pass_rate_min", 0.75),
        )
        add_gate(
            "tool_loop_completion",
            "Tool loop completion",
            tool_loop_completion,
            targets.get("tool_loop_completion_rate_min", 0.8),
        )
        add_gate(
            "tool_loop_success",
            "Tool loop tool success",
            tool_loop_success,
            targets.get("tool_loop_completion_rate_min", 0.8),
        )

        passed_count = sum(1 for gate in gates if gate["passed"])
        overall_passed = passed_count == len(gates) if gates else False

        return {
            "overall_passed": overall_passed,
            "passed_count": passed_count,
            "total_gates": len(gates),
            "gates": gates,
            "targets": targets,
            "journeys": self._load_journeys(),
            "eval_dashboard": eval_dash,
            "agent_metrics": {
                "tool_loop_completion_rate": tool_loop_completion,
                "tool_loop_tool_success_rate": tool_loop_success,
                "health_status": agent_metrics.get("health_status"),
            },
        }

    def journeys_payload(self) -> dict[str, object]:
        targets = self._load_targets()
        return {
            "journeys": self._load_journeys(),
            "kpi_targets": targets,
        }
