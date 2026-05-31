from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from app.domain.schemas import (
    AgentProfileCreateRequest,
    AgentRunRequest,
    AgentRunState,
    TaskType,
)
from app.services.agent_service import AgentService


@dataclass(frozen=True)
class AgentEvalScenario:
    id: str
    category: str
    title: str
    agent_name: str
    system_prompt: str
    input: str
    enabled_tools: list[str]
    use_tool_loop: bool = False
    allow_online: bool = False
    online_url: Optional[str] = None
    memory_seed: Optional[str] = None
    expect_substrings: list[str] | None = None


class AgentEvalService:
    def __init__(
        self,
        scenarios_path: str = "./data/agent_eval_scenarios.json",
        agent_service: Optional[AgentService] = None,
        memory_seed_fn: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._scenarios = self._load_scenarios(scenarios_path)
        self._agent_service = agent_service
        self._memory_seed_fn = memory_seed_fn

    def list_scenarios(self) -> list[dict[str, str]]:
        return [
            {
                "id": item.id,
                "category": item.category,
                "title": item.title,
            }
            for item in self._scenarios
        ]

    def _load_scenarios(self, scenarios_path: str) -> list[AgentEvalScenario]:
        path = Path(scenarios_path)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        result: list[AgentEvalScenario] = []
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            result.append(
                AgentEvalScenario(
                    id=str(raw.get("id", "")),
                    category=str(raw.get("category", "general")),
                    title=str(raw.get("title", "")),
                    agent_name=str(raw.get("agent_name", "Eval Agent")),
                    system_prompt=str(raw.get("system_prompt", "You are an eval agent.")),
                    input=str(raw.get("input", "")),
                    enabled_tools=list(raw.get("enabled_tools", [])),
                    use_tool_loop=bool(raw.get("use_tool_loop", False)),
                    allow_online=bool(raw.get("allow_online", False)),
                    online_url=raw.get("online_url"),
                    memory_seed=raw.get("memory_seed"),
                    expect_substrings=list(raw.get("expect_substrings", [])),
                )
            )
        return result

    async def run_scenario(self, scenario_id: str) -> dict[str, object]:
        if self._agent_service is None:
            raise RuntimeError("AgentEvalService requires AgentService.")
        scenario = next((item for item in self._scenarios if item.id == scenario_id), None)
        if scenario is None:
            raise ValueError(f"Unknown agent eval scenario: {scenario_id}")

        agent = self._agent_service.create_agent(
            AgentProfileCreateRequest(
                name=f"{scenario.agent_name}-{uuid4().hex[:6]}",
                description=f"Eval scenario {scenario.id}",
                system_prompt=scenario.system_prompt,
                task_type=TaskType.general,
                enabled_tools=scenario.enabled_tools,
                use_tool_loop=scenario.use_tool_loop,
                allow_online=scenario.allow_online,
            )
        )
        if scenario.memory_seed and self._memory_seed_fn is not None:
            self._memory_seed_fn(agent.agent_id, scenario.memory_seed)

        started = time.perf_counter()
        payload = AgentRunRequest(
            input=scenario.input,
            online_url=scenario.online_url,
            use_tool_loop=scenario.use_tool_loop,
        )
        try:
            result = await self._agent_service.run_agent(agent.agent_id, payload)
            response = result.response
            success = self._score(scenario, response)
            error = None
        except Exception as exc:  # noqa: BLE001
            response = ""
            success = False
            error = str(exc)

        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "scenario_id": scenario.id,
            "category": scenario.category,
            "title": scenario.title,
            "agent_id": agent.agent_id,
            "success": success,
            "duration_ms": duration_ms,
            "response_excerpt": response[:500],
            "error": error,
        }

    async def run_suite(self, category: str | None = None) -> dict[str, object]:
        selected = self._scenarios
        if category:
            selected = [item for item in self._scenarios if item.category == category]
        results = []
        for scenario in selected:
            results.append(await self.run_scenario(scenario.id))
        passed = sum(1 for item in results if item.get("success"))
        total = len(results)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total) if total else 0.0,
            "results": results,
        }

    @staticmethod
    def _score(scenario: AgentEvalScenario, response: str) -> bool:
        if not response.strip():
            return False
        lowered = response.lower()
        expected = scenario.expect_substrings or []
        if not expected:
            return True
        return any(fragment.lower() in lowered for fragment in expected)
