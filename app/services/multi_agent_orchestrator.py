from __future__ import annotations

import re
import time
from uuid import uuid4

from app.domain.schemas import (
    ChatRequest,
    OrchestrationPhaseResult,
    OrchestrationRunRequest,
    OrchestrationRunResponse,
    TaskCreateRequest,
    TaskMode,
    TaskState,
    TaskType,
)
from app.services.chat_service import ChatService
from app.services.task_service import TaskService


class MultiAgentOrchestrator:
    def __init__(self, task_service: TaskService, chat_service: ChatService) -> None:
        self._tasks = task_service
        self._chat = chat_service

    async def run(self, payload: OrchestrationRunRequest) -> OrchestrationRunResponse:
        run_id = f"orch_{uuid4().hex[:12]}"
        phases: list[OrchestrationPhaseResult] = []

        plan_started = time.perf_counter()
        plan_steps = self._build_plan(payload.input, payload.task_type)
        routing_detail = (
            f"routing_policy={payload.routing_policy}, "
            f"repo_profile={payload.repo_profile or 'auto'}"
        )
        phases.append(
            OrchestrationPhaseResult(
                phase="planner",
                status="passed",
                detail=f"Prepared {len(plan_steps)} execution steps ({routing_detail}).",
                duration_ms=int((time.perf_counter() - plan_started) * 1000),
            )
        )

        execute_started = time.perf_counter()
        executor_prompt = (
            "Execute this coding objective using the approved plan.\n"
            f"Objective: {payload.input}\n"
            f"Plan: {' -> '.join(plan_steps)}"
        )
        chat_result = await self._chat.chat(
            ChatRequest(
                message=executor_prompt,
                task_type=payload.task_type,
                model=payload.model,
                session_id=payload.session_id,
                use_memory=True,
                use_retrieval=payload.use_retrieval,
                retrieval_limit=payload.retrieval_limit,
                retrieval_path_prefix=payload.retrieval_path_prefix,
                repo_profile=payload.repo_profile,
                routing_policy=payload.routing_policy,
            )
        )
        executor_response = chat_result.response or ""
        phases.append(
            OrchestrationPhaseResult(
                phase="executor",
                status="passed" if executor_response.strip() else "failed",
                detail="Executor produced a model response."
                if executor_response.strip()
                else "Executor returned an empty response.",
                duration_ms=int((time.perf_counter() - execute_started) * 1000),
            )
        )

        verify_started = time.perf_counter()
        verify_ok, verify_detail = self._verify(payload.input, executor_response)
        phases.append(
            OrchestrationPhaseResult(
                phase="verifier",
                status="passed" if verify_ok else "failed",
                detail=verify_detail,
                duration_ms=int((time.perf_counter() - verify_started) * 1000),
            )
        )

        task_started = time.perf_counter()
        task = self._tasks.create_task(
            TaskCreateRequest(
                input=f"[orchestration:{run_id}] {payload.input}",
                task_type=payload.task_type,
                mode=TaskMode.auto,
                session_id=chat_result.session_id,
            )
        )
        task_status = self._tasks.get_task(task.task_id)
        task_ok = task_status.state == TaskState.completed
        phases.append(
            OrchestrationPhaseResult(
                phase="task_runner",
                status="passed" if task_ok else "failed",
                detail=f"Task lifecycle finished with state={task_status.state.value}.",
                duration_ms=int((time.perf_counter() - task_started) * 1000),
            )
        )

        overall_ok = all(item.status == "passed" for item in phases)
        report = self._build_report(run_id, plan_steps, phases, executor_response, task_status.report or "")
        return OrchestrationRunResponse(
            run_id=run_id,
            status="completed" if overall_ok else "failed",
            plan_steps=plan_steps,
            phases=phases,
            report=report,
            executor_response=executor_response,
            session_id=chat_result.session_id,
        )

    @staticmethod
    def _build_plan(task_input: str, task_type: TaskType) -> list[str]:
        text = task_input.lower()
        steps = ["analyze_requirements"]
        if task_type in {TaskType.coding, TaskType.debug}:
            steps.append("inspect_workspace")
        if "readme" in text or task_type == TaskType.review:
            steps.append("read_readme")
        if "test" in text or task_type == TaskType.debug:
            steps.append("validate_tests")
        steps.append("compose_delivery")
        return steps

    @staticmethod
    def _verify(task_input: str, response_text: str) -> tuple[bool, str]:
        if not response_text.strip():
            return False, "Verifier failed: empty executor output."
        if len(response_text.strip()) < 24:
            return False, "Verifier failed: response too short to be actionable."
        keywords = re.findall(r"[a-zA-Z]{4,}", task_input.lower())
        if not keywords:
            return True, "Verifier passed with generic response checks."
        matched = sum(1 for word in keywords[:8] if word in response_text.lower())
        if matched == 0 and len(response_text.strip()) < 32:
            return False, "Verifier failed: response does not reflect task intent."
        if matched == 0:
            return True, "Verifier passed with actionable response length threshold."
        return True, f"Verifier passed ({matched} intent terms reflected)."

    @staticmethod
    def _build_report(
        run_id: str,
        plan_steps: list[str],
        phases: list[OrchestrationPhaseResult],
        executor_response: str,
        task_report: str,
    ) -> str:
        lines = [
            f"Multi-agent orchestration report ({run_id})",
            "",
            "Plan:",
            *[f"- {step}" for step in plan_steps],
            "",
            "Phases:",
        ]
        for phase in phases:
            lines.append(
                f"- {phase.phase}: {phase.status} ({phase.duration_ms}ms) — {phase.detail}"
            )
        lines.extend(
            [
                "",
                "Executor excerpt:",
                executor_response[:1200],
                "",
                "Task runner report:",
                task_report or "(no task report)",
            ]
        )
        return "\n".join(lines).strip()
