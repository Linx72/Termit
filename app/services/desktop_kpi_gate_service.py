"""KPI gate evaluation for desktop north-star targets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from app.services.agent_outcome_service import agent_run_success_rate


class DesktopKpiGateService:
    def __init__(
        self,
        north_star_path: str,
        *,
        eval_dashboard_provider: Callable[[], dict[str, object]],
        agent_metrics_provider: Callable[[], dict[str, object]],
        telemetry_summary_provider: Callable[[], dict[str, object]] | None = None,
        metrics_summary_provider: Callable[[], dict[str, object]] | None = None,
        beta_metrics_provider: Callable[[], dict[str, object]] | None = None,
        onboarding_metrics_provider: Callable[[], dict[str, object]] | None = None,
        mcp_metrics_provider: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        self._path = Path(north_star_path)
        self._eval_dashboard_provider = eval_dashboard_provider
        self._agent_metrics_provider = agent_metrics_provider
        self._telemetry_summary_provider = telemetry_summary_provider
        self._metrics_summary_provider = metrics_summary_provider
        self._beta_metrics_provider = beta_metrics_provider
        self._onboarding_metrics_provider = onboarding_metrics_provider
        self._mcp_metrics_provider = mcp_metrics_provider

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
        tl_runs_recent = int(agent_metrics.get("tool_loop_runs_recent", 0) or 0)
        tl_window_runs = int(agent_metrics.get("tool_loop_runs_recent_window", 0) or 0)
        if tl_window_runs >= 5:
            tool_loop_completion = float(
                agent_metrics.get("tool_loop_completion_rate_recent_window") or tool_loop_completion
            )
            tool_loop_success = float(
                agent_metrics.get("tool_loop_tool_success_rate_recent_window") or tool_loop_success
            )
        elif tl_runs_recent >= 5:
            tool_loop_completion = float(
                agent_metrics.get("tool_loop_completion_rate_recent") or tool_loop_completion
            )
            tool_loop_success = float(
                agent_metrics.get("tool_loop_tool_success_rate_recent") or tool_loop_success
            )
        by_outcome_raw = agent_metrics.get("by_outcome_class") or {}
        outcome_map = (
            {str(k): int(v) for k, v in by_outcome_raw.items()}
            if isinstance(by_outcome_raw, dict)
            else {}
        )
        run_success_rate, terminal_runs = agent_run_success_rate(outcome_map)

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
            targets.get("tool_loop_tool_success_rate_min", targets.get("tool_loop_completion_rate_min", 0.8)),
        )

        by_outcome = agent_metrics.get("by_outcome_class") or {}
        if isinstance(by_outcome, dict):
            min_terminal = int(targets.get("agent_run_terminal_min", 5) or 5)
            if terminal_runs >= min_terminal:
                add_gate(
                    "agent_run_success_rate",
                    "Agent run success (outcome)",
                    run_success_rate,
                    targets.get("agent_run_success_rate_min", targets.get("task_success_rate_min", 0.75)),
                )

        metrics_summary: dict[str, object] = {}
        if self._metrics_summary_provider is not None:
            metrics_summary = self._metrics_summary_provider()
            task_total = int(metrics_summary.get("task_total", 0) or 0)
            if task_total > 0:
                add_gate(
                    "task_success_rate",
                    "Task success rate",
                    float(metrics_summary.get("task_success_rate", 0.0)),
                    targets.get("task_success_rate_min", 0.75),
                )
                add_gate(
                    "automation_rate",
                    "Automation rate",
                    float(metrics_summary.get("automation_rate", 0.0)),
                    targets.get("automation_rate_min", 0.6),
                )
            chat_total = int(metrics_summary.get("chat_requests_total", 0) or 0)
            recent_n = int(metrics_summary.get("chat_recent_sample_size", 0) or 0)
            if chat_total > 0:
                chat_p95 = float(metrics_summary.get("chat_latency_p95_ms", 0.0))
                if recent_n >= 5:
                    chat_p95 = float(metrics_summary.get("chat_latency_p95_recent_ms", chat_p95) or chat_p95)
                add_gate(
                    "chat_p95_ttft_ms",
                    "Chat p95 TTFT (ms)",
                    chat_p95,
                    targets.get("chat_p95_ttft_ms_max", 3000.0),
                    higher_is_better=False,
                )

        if self._beta_metrics_provider is not None:
            beta = self._beta_metrics_provider()
            cohort_d30 = int(beta.get("cohort_size_d30", 0) or 0)
            d30_rate = beta.get("d30_retention_rate")
            if cohort_d30 >= 5 and isinstance(d30_rate, (int, float)):
                add_gate(
                    "d30_retention",
                    "D30 retention (beta)",
                    float(d30_rate),
                    targets.get("d30_retention_min", 0.35),
                )

        if self._onboarding_metrics_provider is not None:
            onboarding = self._onboarding_metrics_provider()
            assigned = int(onboarding.get("total_assigned", 0) or 0)
            conversion = onboarding.get("overall_conversion_rate")
            if assigned >= 5 and isinstance(conversion, (int, float)):
                add_gate(
                    "onboarding_conversion",
                    "Onboarding conversion",
                    float(conversion),
                    targets.get("onboarding_conversion_min", 0.5),
                )

        mcp_metrics: dict[str, object] = {}
        if self._mcp_metrics_provider is not None:
            mcp_metrics = self._mcp_metrics_provider()
            mcp_active = int(mcp_metrics.get("mcp_active_runs", 0) or 0)
            tool_loop_runs = int(mcp_metrics.get("tool_loop_runs", 0) or 0)
            if mcp_active >= 5:
                add_gate(
                    "mcp_inject_rate",
                    "MCP context inject rate",
                    float(mcp_metrics.get("mcp_inject_rate", 0.0)),
                    targets.get("mcp_inject_rate_min", 0.2),
                )
            if tool_loop_runs >= 10:
                adoption = mcp_metrics.get("mcp_adoption_rate")
                if isinstance(adoption, (int, float)):
                    add_gate(
                        "mcp_adoption_rate",
                        "MCP adoption (runs with MCP / tool loop runs)",
                        float(adoption),
                        targets.get("mcp_adoption_rate_min", 0.05),
                    )

        telemetry: dict[str, object] = {}
        if self._telemetry_summary_provider is not None:
            telemetry = self._telemetry_summary_provider()
            ttfuc = telemetry.get("ttfuc_median_seconds")
            if isinstance(ttfuc, (int, float)):
                add_gate(
                    "ttfuc_seconds",
                    "TTFUC median (s)",
                    float(ttfuc),
                    targets.get("ttfuc_seconds", 90.0),
                    higher_is_better=False,
                )
            patch_rate = telemetry.get("patch_acceptance_rate")
            if isinstance(patch_rate, (int, float)) and float(patch_rate) > 0:
                add_gate(
                    "patch_acceptance_rate",
                    "Patch acceptance rate",
                    float(patch_rate),
                    targets.get("patch_acceptance_rate", 0.7),
                )
            verify_rate = telemetry.get("verify_pass_rate")
            if isinstance(verify_rate, (int, float)) and int(telemetry.get("verify_ok", 0) or 0) + int(
                telemetry.get("verify_fail", 0) or 0
            ) > 0:
                add_gate(
                    "verify_pass_rate",
                    "Verify pass rate",
                    float(verify_rate),
                    targets.get("verify_pass_rate", 0.85),
                )
            resume_med = telemetry.get("agent_resume_median_seconds")
            if isinstance(resume_med, (int, float)):
                add_gate(
                    "agent_resume_median_seconds",
                    "Agent resume median (s)",
                    float(resume_med),
                    targets.get("agent_resume_median_seconds", 30.0),
                    higher_is_better=False,
                )
            local_share = telemetry.get("local_only_task_share")
            if isinstance(local_share, (int, float)) and int(telemetry.get("agent_runs_total", 0) or 0) > 0:
                add_gate(
                    "local_only_task_share",
                    "Local-only task share",
                    float(local_share),
                    targets.get("local_only_task_share", 0.6),
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
                "by_outcome_class": outcome_map,
                "agent_run_success_rate": run_success_rate,
                "agent_run_terminal_total": terminal_runs,
            },
            "telemetry": telemetry,
            "metrics_summary": metrics_summary,
            "mcp_metrics": mcp_metrics,
        }

    def journeys_payload(self) -> dict[str, object]:
        targets = self._load_targets()
        return {
            "journeys": self._load_journeys(),
            "kpi_targets": targets,
        }
