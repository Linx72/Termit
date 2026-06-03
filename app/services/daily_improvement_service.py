"""Plan and execute daily self-improvement actions for Termit agents."""

from __future__ import annotations

from typing import Callable, Optional

from app.core.config import Settings
from app.domain.schemas import AgentProfileCreateRequest, AgentRunRequest
from app.services.agent_service import AgentNotFoundError, AgentService
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.desktop_kpi_gate_service import DesktopKpiGateService
from app.services.eval_service import EvalService
from app.services.finetune_service import FinetuneService


class DailyImprovementService:
    """Diagnose KPI/eval/DLQ gaps and enqueue targeted agent improvement runs."""

    IMPROVEMENT_AGENT_NAME = "Termit Self-Improvement"

    def __init__(
        self,
        *,
        settings: Settings,
        agent_service: AgentService,
        eval_service: EvalService,
        kpi_gate_service: DesktopKpiGateService,
        finetune_service: FinetuneService,
        templates_store: AgentTemplatesStore | None = None,
    ) -> None:
        self._settings = settings
        self._agent_service = agent_service
        self._eval_service = eval_service
        self._kpi_gate_service = kpi_gate_service
        self._finetune_service = finetune_service
        self._templates_store = templates_store or AgentTemplatesStore(settings.agent_templates_path)

    def resolve_agent_id(self) -> tuple[Optional[str], str]:
        configured = self._settings.daily_improvement_agent_id.strip()
        if configured:
            try:
                self._agent_service.get_agent(configured)
            except AgentNotFoundError:
                return None, f"Configured agent not found: {configured}"
            return configured, "configured"

        for agent in self._agent_service.list_agents():
            tools = set(agent.enabled_tools)
            if agent.use_tool_loop and {"apply_patch", "read_file"}.issubset(tools):
                return agent.agent_id, "registry_match"
            if agent.task_type.value == "coding" and agent.use_tool_loop:
                return agent.agent_id, "coding_tool_loop"

        if not self._settings.daily_improvement_auto_create_agent:
            return None, "no_suitable_agent"

        try:
            payload = self._templates_store.to_create_request("fix-ci")
        except ValueError:
            payload = AgentProfileCreateRequest(
                name=self.IMPROVEMENT_AGENT_NAME,
                description="Autonomous daily project improvement",
                system_prompt=(
                    "You improve the Termit codebase daily. Read code, apply minimal patches, "
                    "run tests, and capture learnings."
                ),
                task_type="coding",
                enabled_tools=["read_file", "search_repo", "apply_patch", "execute_command"],
                use_tool_loop=True,
                use_retrieval=True,
            )
        else:
            payload = payload.model_copy(
                update={
                    "name": self.IMPROVEMENT_AGENT_NAME,
                    "description": "Autonomous daily project improvement (from fix-ci template)",
                }
            )

        for agent in self._agent_service.list_agents():
            if agent.name == self.IMPROVEMENT_AGENT_NAME:
                return agent.agent_id, "existing_self_improvement_agent"

        created = self._agent_service.create_agent(payload)
        return created.agent_id, "created_from_template"

    def build_plan(self) -> dict[str, object]:
        gates = self._kpi_gate_service.evaluate_gates()
        eval_dashboard = self._eval_service.build_dashboard(report_limit=3)
        tuning_report = self._finetune_service.tuning_report()
        dlq = self._agent_service.list_dlq_runs(limit=self._settings.daily_improvement_max_dlq_replay)
        failed_scenarios = self._failed_eval_scenarios(eval_dashboard)
        recommendations = list(tuning_report.get("recommendations", []))

        actions: list[dict[str, object]] = []
        priority = 0

        if dlq.total > 0:
            priority += 1
            actions.append(
                {
                    "type": "replay_dlq",
                    "priority": priority,
                    "limit": min(dlq.total, self._settings.daily_improvement_max_dlq_replay),
                    "reason": f"{dlq.total} dead-letter run(s) to replay",
                }
            )

        for scenario in failed_scenarios[: self._settings.daily_improvement_max_eval_fixes]:
            priority += 1
            actions.append(
                {
                    "type": "agent_run",
                    "priority": priority,
                    "reason": f"eval_failed:{scenario.get('scenario_id')}",
                    "instruction": self._eval_fix_instruction(scenario),
                    "policy_preset": "solo",
                    "use_tool_loop": True,
                    "use_retrieval": True,
                }
            )

        if not gates.get("overall_passed", True):
            for gate in gates.get("gates", []):
                if gate.get("passed"):
                    continue
                gate_id = str(gate.get("gate_id", ""))
                if gate_id == "eval_pass_rate" and not any(
                    item.get("type") == "eval_probe" for item in actions
                ):
                    priority += 1
                    actions.append(
                        {
                            "type": "eval_probe",
                            "priority": priority,
                            "limit": self._settings.daily_improvement_eval_probe_limit,
                            "reason": "KPI gate: eval pass rate below target",
                        }
                    )
                instruction = self._kpi_gate_instruction(gate, recommendations)
                if instruction:
                    priority += 1
                    actions.append(
                        {
                            "type": "agent_run",
                            "priority": priority,
                            "reason": f"kpi_gate:{gate_id}",
                            "instruction": instruction,
                            "policy_preset": "solo",
                            "use_tool_loop": True,
                            "use_retrieval": True,
                        }
                    )

        if not actions and recommendations:
            priority += 1
            actions.append(
                {
                    "type": "agent_run",
                    "priority": priority,
                    "reason": "tuning_recommendations",
                    "instruction": self._tuning_instruction(recommendations),
                    "policy_preset": "solo",
                    "use_tool_loop": True,
                    "use_retrieval": True,
                }
            )

        if self._settings.daily_improvement_run_eval_probe and not any(
            item.get("type") == "eval_probe" for item in actions
        ):
            priority += 1
            actions.append(
                {
                    "type": "eval_probe",
                    "priority": priority,
                    "limit": self._settings.daily_improvement_eval_probe_limit,
                    "reason": "daily health probe",
                }
            )

        agent_runs = [item for item in actions if item.get("type") == "agent_run"]
        if len(agent_runs) > self._settings.daily_improvement_max_agent_runs:
            keep_ids = {
                id(item)
                for item in sorted(agent_runs, key=lambda row: int(row.get("priority", 0)))[
                    : self._settings.daily_improvement_max_agent_runs
                ]
            }
            actions = [
                item
                for item in actions
                if item.get("type") != "agent_run" or id(item) in keep_ids
            ]

        actions.sort(key=lambda item: int(item.get("priority", 0)))
        return {
            "diagnostics": {
                "kpi_overall_passed": gates.get("overall_passed"),
                "kpi_gates": gates.get("gates", []),
                "eval_pass_rate": eval_dashboard.get("pass_rate"),
                "failed_eval_scenarios": failed_scenarios,
                "dlq_count": dlq.total,
                "tuning_recommendations": recommendations,
            },
            "actions": actions,
            "action_count": len(actions),
        }

    def execute_plan(
        self,
        plan: dict[str, object],
        *,
        source: str,
    ) -> dict[str, object]:
        agent_id, agent_source = self.resolve_agent_id()
        if agent_id is None:
            return {
                "status": "skipped",
                "source": source,
                "detail": agent_source,
                "plan": plan,
                "results": [],
            }

        results: list[dict[str, object]] = []
        for action in plan.get("actions", []):
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("type", ""))
            if action_type == "replay_dlq":
                limit = int(action.get("limit", self._settings.daily_improvement_max_dlq_replay))
                replayed = self._agent_service.replay_dlq(limit=limit)
                results.append(
                    {
                        "type": action_type,
                        "reason": action.get("reason"),
                        "count": len(replayed),
                        "run_ids": [item.run_id for item in replayed],
                    }
                )
                continue

            if action_type == "eval_probe":
                limit = int(action.get("limit", self._settings.daily_improvement_eval_probe_limit))
                report = self._eval_service.run_suite(limit=limit, persist_report=True)
                results.append(
                    {
                        "type": action_type,
                        "reason": action.get("reason"),
                        "run_id": report.get("run_id"),
                        "pass_rate": report.get("pass_rate"),
                        "total": report.get("total"),
                    }
                )
                continue

            if action_type == "agent_run":
                instruction = str(action.get("instruction", "")).strip()
                if not instruction:
                    continue
                payload = AgentRunRequest(
                    input=instruction,
                    use_tool_loop=bool(action.get("use_tool_loop", True)),
                    use_retrieval=bool(action.get("use_retrieval", True)),
                    policy_preset=str(action.get("policy_preset") or "solo"),
                    priority=min(90, 10 + int(action.get("priority", 0))),
                    workspace_scope=".",
                )
                created = self._agent_service.create_run(agent_id, payload)
                results.append(
                    {
                        "type": action_type,
                        "reason": action.get("reason"),
                        "agent_id": agent_id,
                        "run_id": created.run_id,
                        "state": created.state.value,
                    }
                )

        return {
            "status": "executed",
            "source": source,
            "agent_id": agent_id,
            "agent_source": agent_source,
            "plan": plan,
            "results": results,
        }

    @staticmethod
    def _failed_eval_scenarios(eval_dashboard: dict[str, object]) -> list[dict[str, object]]:
        reports = eval_dashboard.get("recent_reports", [])
        if not isinstance(reports, list) or not reports:
            return []
        latest = reports[0]
        if not isinstance(latest, dict):
            return []
        results = latest.get("results", [])
        if not isinstance(results, list):
            return []
        failed: list[dict[str, object]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            if item.get("status") == "passed":
                continue
            failed.append(
                {
                    "scenario_id": item.get("scenario_id"),
                    "category": item.get("category"),
                    "message": item.get("message"),
                    "failure_class": item.get("failure_class"),
                    "prompt": item.get("prompt"),
                }
            )
        return failed

    @staticmethod
    def _eval_fix_instruction(scenario: dict[str, object]) -> str:
        scenario_id = scenario.get("scenario_id", "unknown")
        category = scenario.get("category", "general")
        message = scenario.get("message", "Scenario failed")
        prompt = scenario.get("prompt") or scenario.get("instruction") or ""
        return (
            "Daily self-improvement: fix a failing eval scenario in the Termit repo.\n"
            f"Scenario ID: {scenario_id}\n"
            f"Category: {category}\n"
            f"Failure: {message}\n"
            f"Prompt: {prompt}\n\n"
            "Steps: locate root cause, apply minimal patch, run relevant tests "
            "(python3 -m unittest discover -s tests -q), report what changed."
        )

    @staticmethod
    def _kpi_gate_instruction(gate: dict[str, object], recommendations: list[str]) -> str:
        gate_id = str(gate.get("gate_id", ""))
        label = str(gate.get("label", gate_id))
        actual = gate.get("actual")
        target = gate.get("target")
        lines = [
            "Daily self-improvement: improve Termit agent quality KPI.",
            f"Gate: {label} ({gate_id})",
            f"Actual: {actual} · Target: {target}",
        ]
        if recommendations:
            lines.append("Tuning hints:")
            lines.extend(f"- {item}" for item in recommendations[:3])
        if gate_id.startswith("tool_loop"):
            lines.append(
                "Focus on tool loop reliability: JSON action parsing, verify-after-patch, "
                "and anti-loop step budget."
            )
        elif gate_id == "eval_pass_rate":
            lines.append(
                "Focus on eval pass rate: run targeted fixes for failing scenarios and add tests."
            )
        lines.append(
            "Apply minimal safe changes, run tests, and avoid unrelated refactors."
        )
        return "\n".join(lines)

    @staticmethod
    def _tuning_instruction(recommendations: list[str]) -> str:
        lines = [
            "Daily self-improvement: address tool-loop tuning recommendations.",
            * [f"- {item}" for item in recommendations[:5]],
            "Implement the smallest effective prompt/tool/policy change and verify with tests.",
        ]
        return "\n".join(lines)
