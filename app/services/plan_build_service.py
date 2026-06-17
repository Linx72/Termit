from __future__ import annotations

import threading
from typing import Optional

from fastapi import HTTPException

from app.domain.schemas import AgentRunRequest, BuildFromPlanRequest, BuildFromPlanResponse
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_service import AgentQueueFullError, AgentService, GuardrailBlockedError
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.trace_span_store import TraceSpanStore


class PlanBuildService:
    """Enqueue agent runs from an approved plan (Plan → Build parity)."""

    def __init__(
        self,
        agent_service: AgentService,
        registry: AgentRegistryStore,
        templates: AgentTemplatesStore,
        *,
        trace_spans: TraceSpanStore | None = None,
    ) -> None:
        self._agents = agent_service
        self._registry = registry
        self._templates = templates
        self._trace_spans = trace_spans
        self._metrics_lock = threading.Lock()
        self._plan_build_enqueued_total = 0

    def metrics_snapshot(self) -> dict[str, float]:
        with self._metrics_lock:
            return {"plan_build_enqueued_total": float(self._plan_build_enqueued_total)}

    def enqueue(self, payload: BuildFromPlanRequest) -> BuildFromPlanResponse:
        agent_id = self._resolve_agent_id(payload.agent_id, payload.template_id)
        input_text = self._format_input(payload.plan_text, payload.objective)
        run_payload = AgentRunRequest(
            input=input_text,
            session_id=payload.session_id,
            run_mode="agent",
            use_tool_loop=True,
            verify_after_patch=True if payload.verify_after_patch else None,
            parent_run_id=payload.plan_run_id,
            priority=payload.priority,
        )
        try:
            created = self._agents.create_run(agent_id, run_payload)
        except GuardrailBlockedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentQueueFullError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc

        if self._trace_spans is not None and payload.plan_run_id:
            self._trace_spans.record(
                run_id=payload.plan_run_id,
                name="plan.build_enqueue",
                status="ok",
                detail=f"child_run={created.run_id}",
            )

        with self._metrics_lock:
            self._plan_build_enqueued_total += 1

        preview = input_text[:240] + ("…" if len(input_text) > 240 else "")
        return BuildFromPlanResponse(
            run_id=created.run_id,
            agent_id=agent_id,
            state=created.state.value,
            queued_position=created.queued_position,
            input_preview=preview,
        )

    def _resolve_agent_id(self, agent_id: Optional[str], template_id: Optional[str]) -> str:
        if agent_id and agent_id.strip():
            profile = self._registry.get_agent(agent_id.strip())
            if profile is None:
                raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
            return profile.agent_id
        tid = (template_id or "desktop-cursor-parity-stable").strip()
        try:
            request = self._templates.to_create_request(tid)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        for agent in self._registry.list_agents():
            if agent.name == request.name and agent.task_type == request.task_type:
                return agent.agent_id
        return self._registry.create_agent(request).agent_id

    @staticmethod
    def _format_input(plan_text: str, objective: Optional[str]) -> str:
        goal = (objective or "").strip() or "Implement the approved plan."
        return (
            "Implement the approved plan below step by step using tools "
            "(read_file, apply_patch, execute_command). Do not replan unless blocked.\n\n"
            f"Objective: {goal}\n\n"
            "Plan:\n"
            f"{plan_text.strip()}\n"
        )
