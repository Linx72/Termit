from __future__ import annotations

import asyncio
import re
import threading
import time
from uuid import uuid4

from app.domain.schemas import (
    OrchestrationActionObservation,
    ChatMessage,
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
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.task_service import TaskService
from app.services.tooling_service import ToolingService
from app.services.verify_command_resolver import resolve_verify_command


class MultiAgentOrchestrator:
    def __init__(
        self,
        task_service: TaskService,
        chat_service: ChatService,
        tooling: ToolingService | None = None,
        code_retrieval: CodeRetrievalService | None = None,
        openhands_contract_enabled: bool = False,
    ) -> None:
        self._tasks = task_service
        self._chat = chat_service
        self._tooling = tooling
        self._retrieval = code_retrieval
        self._openhands_contract_enabled = bool(openhands_contract_enabled)
        self._max_coder_attempts = 2
        self._metrics_lock = threading.Lock()
        self._metrics: dict[str, float] = {
            "orchestration_runs_total": 0,
            "coder_attempts_total": 0,
            "coder_retry_runs_total": 0,
            "coder_retry_success_runs_total": 0,
            "reviewer_reject_total": 0,
            "openhands_contract_runs_total": 0,
            "openhands_contract_actions_total": 0,
        }

    async def run(self, payload: OrchestrationRunRequest) -> OrchestrationRunResponse:
        run_id = f"orch_{uuid4().hex[:12]}"
        phases: list[OrchestrationPhaseResult] = []
        action_observation: list[OrchestrationActionObservation] = []
        with self._metrics_lock:
            self._metrics["orchestration_runs_total"] += 1

        plan_started = time.perf_counter()
        plan_steps = await self._planner_steps(payload)
        phases.append(
            OrchestrationPhaseResult(
                phase="planner",
                status="passed",
                detail=f"Prepared {len(plan_steps)} execution steps.",
                duration_ms=int((time.perf_counter() - plan_started) * 1000),
            )
        )
        self._append_contract_item(
            action_observation,
            action="planner.plan",
            observation=f"Prepared {len(plan_steps)} execution steps.",
        )

        explore_started = time.perf_counter()
        explore_detail = await self._parallel_explore(payload)
        phases.append(
            OrchestrationPhaseResult(
                phase="explore",
                status="passed" if explore_detail else "skipped",
                detail=explore_detail or "Explore skipped.",
                duration_ms=int((time.perf_counter() - explore_started) * 1000),
            )
        )
        self._append_contract_item(
            action_observation,
            action="explore.context",
            observation=explore_detail or "Explore skipped.",
        )

        if payload.plan_only:
            report = "\n".join(
                [
                    f"Plan-only orchestration {run_id}",
                    f"Objective: {payload.input}",
                    "Plan:",
                    *[f"- {step}" for step in plan_steps],
                    "",
                    "Explore:",
                    explore_detail or "(none)",
                    "",
                    "Next: rerun with plan_only=false or enqueue agent run to Build.",
                ]
            )
            return OrchestrationRunResponse(
                run_id=run_id,
                status="plan_ready",
                plan_steps=plan_steps,
                phases=phases,
                action_observation=action_observation if self._openhands_contract_enabled else [],
                report=report,
                executor_response="",
                session_id=payload.session_id,
            )

        from app.services.cross_platform_dev_service import CrossPlatformDevService

        execute_started = time.perf_counter()
        chat_result_session = payload.session_id
        review_detail = ""
        review_ok = False
        if CrossPlatformDevService.is_cross_platform_task(payload.input):
            executor_response, atomic_phases, chat_result_session = await self._atomic_build_phases(
                payload,
                explore_detail=explore_detail,
            )
            phases.extend(atomic_phases)
            review_started = time.perf_counter()
            review_detail, review_ok = await self._reviewer_phase(payload.input, executor_response)
            phases.append(
                OrchestrationPhaseResult(
                    phase="reviewer",
                    status="passed" if review_ok else "failed",
                    detail=review_detail,
                    duration_ms=int((time.perf_counter() - review_started) * 1000),
                )
            )
            self._append_contract_item(
                action_observation,
                action="executor.atomic",
                observation=f"Atomic build finished with review_ok={review_ok}.",
            )
        else:
            executor_prompt = (
                "Execute this coding objective using the approved plan and exploration context.\n"
                f"Objective: {payload.input}\n"
                f"Plan: {' -> '.join(plan_steps)}\n"
                f"Explore:\n{explore_detail or '(none)'}"
            )
            (
                executor_response,
                chat_result_session,
                attempt_count,
                review_detail,
                review_ok,
                attempt_contract,
            ) = await self._mini_coder_loop(payload, executor_prompt)
            action_observation.extend(attempt_contract)
            with self._metrics_lock:
                self._metrics["coder_attempts_total"] += float(attempt_count)
                if attempt_count > 1:
                    self._metrics["coder_retry_runs_total"] += 1
                    if review_ok:
                        self._metrics["coder_retry_success_runs_total"] += 1
                if not review_ok:
                    self._metrics["reviewer_reject_total"] += 1
            phases.append(
                OrchestrationPhaseResult(
                    phase="coder",
                    status="passed" if executor_response.strip() else "failed",
                    detail=f"Coder produced a model response in {attempt_count} attempt(s)."
                    if executor_response.strip()
                    else f"Coder returned an empty response after {attempt_count} attempt(s).",
                    duration_ms=int((time.perf_counter() - execute_started) * 1000),
                )
            )
            self._append_contract_item(
                action_observation,
                action="reviewer.final",
                observation=review_detail,
            )
            phases.append(
                OrchestrationPhaseResult(
                    phase="reviewer",
                    status="passed" if review_ok else "failed",
                    detail=review_detail,
                    duration_ms=0,
                )
            )

        verify_started = time.perf_counter()
        verify_ok, verify_detail = await self._verifier_phase(payload, executor_response)
        phases.append(
            OrchestrationPhaseResult(
                phase="verifier",
                status="passed" if verify_ok else "failed",
                detail=verify_detail,
                duration_ms=int((time.perf_counter() - verify_started) * 1000),
            )
        )
        self._append_contract_item(
            action_observation,
            action="verifier.check",
            observation=verify_detail,
        )

        task_started = time.perf_counter()
        task = self._tasks.create_task(
            TaskCreateRequest(
                input=f"[orchestration:{run_id}] {payload.input}",
                task_type=payload.task_type,
                mode=TaskMode.auto,
                session_id=chat_result_session,
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
        self._append_contract_item(
            action_observation,
            action="task_runner.lifecycle",
            observation=f"Task ended with state={task_status.state.value}.",
        )

        if self._openhands_contract_enabled:
            with self._metrics_lock:
                self._metrics["openhands_contract_runs_total"] += 1
                self._metrics["openhands_contract_actions_total"] += float(len(action_observation))
            phases.append(
                OrchestrationPhaseResult(
                    phase="openhands_contract",
                    status="passed",
                    detail=f"Captured {len(action_observation)} action/observation pairs.",
                    duration_ms=0,
                )
            )

        overall_ok = all(item.status in {"passed", "skipped"} for item in phases)
        report = self._build_report(
            run_id,
            plan_steps,
            phases,
            executor_response,
            task_status.report or "",
            action_observation if self._openhands_contract_enabled else [],
        )
        return OrchestrationRunResponse(
            run_id=run_id,
            status="completed" if overall_ok else "failed",
            plan_steps=plan_steps,
            phases=phases,
            action_observation=action_observation if self._openhands_contract_enabled else [],
            report=report,
            executor_response=executor_response,
            session_id=chat_result_session,
        )

    def metrics_snapshot(self) -> dict[str, float]:
        with self._metrics_lock:
            snapshot = dict(self._metrics)
        runs = max(1.0, snapshot["orchestration_runs_total"])
        retry_runs = snapshot["coder_retry_runs_total"]
        retry_success = snapshot["coder_retry_success_runs_total"]
        snapshot["avg_coder_attempts"] = round(snapshot["coder_attempts_total"] / runs, 4)
        snapshot["coder_retry_run_rate"] = round(retry_runs / runs, 4)
        snapshot["coder_retry_success_rate"] = (
            round(retry_success / retry_runs, 4) if retry_runs > 0 else 0.0
        )
        return snapshot

    async def _atomic_build_phases(
        self,
        payload: OrchestrationRunRequest,
        *,
        explore_detail: str,
    ) -> tuple[str, list[OrchestrationPhaseResult], str | None]:
        from app.services.cross_platform_dev_service import CrossPlatformDevService

        service = CrossPlatformDevService()
        profile, platforms, tasks = service.decompose(payload.input)
        phases: list[OrchestrationPhaseResult] = []
        chunks: list[str] = []
        session_id = payload.session_id

        for index, task in enumerate(tasks):
            step_started = time.perf_counter()
            prompt = service.format_atomic_prompt(
                payload.input,
                profile,
                platforms,
                task,
                index=index,
                total=len(tasks),
            )
            if explore_detail and index == 0:
                prompt = f"{prompt}\n\nExplore context:\n{explore_detail}"
            try:
                result = await self._chat.chat(
                    ChatRequest(
                        message=prompt,
                        task_type=payload.task_type,
                        model=payload.model,
                        session_id=session_id,
                        use_memory=True,
                        use_retrieval=payload.use_retrieval,
                        retrieval_limit=payload.retrieval_limit,
                        retrieval_path_prefix=payload.retrieval_path_prefix,
                        repo_profile=payload.repo_profile,
                        routing_policy=payload.routing_policy,
                        history=[
                            ChatMessage(
                                role="system",
                                content=service.build_agent_context(payload.input, stack_id=profile.stack_id),
                            )
                        ],
                    )
                )
                session_id = result.session_id or session_id
                text = (result.response or "").strip()
                ok = len(text) >= 16
                chunks.append(f"### {task.step_id}\n{text[:2000]}")
            except Exception as exc:  # noqa: BLE001
                ok = False
                text = str(exc)
                chunks.append(f"### {task.step_id}\nerror: {text}")
            phases.append(
                OrchestrationPhaseResult(
                    phase=f"atomic_{task.step_id}",
                    status="passed" if ok else "failed",
                    detail=task.title[:240],
                    duration_ms=int((time.perf_counter() - step_started) * 1000),
                )
            )
            if not ok:
                break

        combined = "\n\n".join(chunks).strip()
        return combined, phases, session_id

    async def _planner_steps(self, payload: OrchestrationRunRequest) -> list[str]:
        planner_prompt = (
            "Decompose the task into 3-6 short execution steps as a numbered list only.\n"
            f"Task: {payload.input}"
        )
        try:
            result = await self._chat.chat(
                ChatRequest(
                    message=planner_prompt,
                    task_type=TaskType.general,
                    model=payload.model,
                    session_id=payload.session_id,
                    use_memory=False,
                    use_retrieval=False,
                    history=[ChatMessage(role="system", content="You are the planner agent.")],
                )
            )
            lines = [
                line.strip(" -")
                for line in result.response.splitlines()
                if line.strip()
            ]
            steps = [line.split(". ", 1)[-1] for line in lines if len(line) > 2][:6]
            if len(steps) >= 3:
                return steps
        except Exception:  # noqa: BLE001
            pass
        return self._build_plan(payload.input, payload.task_type)

    async def _parallel_explore(self, payload: OrchestrationRunRequest) -> str:
        if not payload.use_retrieval:
            return ""

        async def retrieval_part() -> str:
            if self._retrieval is None:
                return ""
            hits = await asyncio.to_thread(
                self._retrieval.search,
                payload.input,
                limit=min(payload.retrieval_limit, 5),
                path_prefix=payload.retrieval_path_prefix,
            )
            if not hits:
                return "retrieval: 0 hits"
            lines = [f"- {hit.path} (score={hit.score:.2f})" for hit in hits[:5]]
            return "retrieval hits:\n" + "\n".join(lines)

        async def list_part() -> str:
            if self._tooling is None:
                return ""
            from app.domain.schemas import ListFilesRequest

            try:
                listing = await asyncio.to_thread(
                    self._tooling.list_files,
                    ListFilesRequest(path=payload.retrieval_path_prefix or ".", pattern="*"),
                )
                return f"workspace files: {len(listing.files)}"
            except Exception as exc:  # noqa: BLE001
                return f"workspace list error: {exc}"

        retrieval_text, list_text = await asyncio.gather(retrieval_part(), list_part())
        parts = [part for part in (retrieval_text, list_text) if part.strip()]
        return "\n".join(parts)

    async def _reviewer_phase(self, task_input: str, executor_response: str) -> tuple[str, bool]:
        if not executor_response.strip():
            return "Reviewer failed: empty coder output.", False
        review_prompt = (
            "Review the coder output for correctness and safety. "
            "Respond with APPROVED or list concrete issues.\n"
            f"Task: {task_input}\n\nOutput:\n{executor_response[:4000]}"
        )
        try:
            result = await self._chat.chat(
                ChatRequest(
                    message=review_prompt,
                    task_type=TaskType.review,
                    use_memory=False,
                    use_retrieval=False,
                    history=[ChatMessage(role="system", content="You are the read-only reviewer agent.")],
                )
            )
            text = result.response.strip()
            normalized = text.upper()
            if normalized.startswith("APPROVED"):
                ok = True
            elif any(
                marker in normalized
                for marker in ("ISSUE", "FAILED", "REJECT", "NOT APPROVED", "BLOCKER", "CHANGES REQUIRED")
            ):
                ok = False
            else:
                ok = len(text) >= 24
            return text[:500], ok
        except Exception as exc:  # noqa: BLE001
            return f"Reviewer error: {exc}", False

    async def _mini_coder_loop(
        self,
        payload: OrchestrationRunRequest,
        executor_prompt: str,
    ) -> tuple[str, str | None, int, str, bool, list[OrchestrationActionObservation]]:
        """mini-swe-agent style retry loop: coder -> reviewer feedback -> coder."""
        feedback = ""
        executor_response = ""
        session_id = payload.session_id
        review_detail = "Reviewer phase did not run."
        review_ok = False
        contract: list[OrchestrationActionObservation] = []

        for attempt in range(1, self._max_coder_attempts + 1):
            message = executor_prompt
            if feedback:
                message = (
                    f"{executor_prompt}\n\nReviewer issues to fix before finalizing:\n"
                    f"{feedback}\n\nAddress every issue explicitly."
                )
            chat_result = await self._chat.chat(
                ChatRequest(
                    message=message,
                    task_type=payload.task_type,
                    model=payload.model,
                    session_id=session_id,
                    use_memory=True,
                    use_retrieval=payload.use_retrieval,
                    retrieval_limit=payload.retrieval_limit,
                    retrieval_path_prefix=payload.retrieval_path_prefix,
                    repo_profile=payload.repo_profile,
                    routing_policy=payload.routing_policy,
                    history=[ChatMessage(role="system", content="You are the coder agent.")],
                )
            )
            session_id = chat_result.session_id
            executor_response = chat_result.response or ""
            self._append_contract_item(
                contract,
                action=f"coder.attempt_{attempt}",
                observation=(executor_response or "").strip()[:500] or "empty response",
            )
            review_detail, review_ok = await self._reviewer_phase(payload.input, executor_response)
            self._append_contract_item(
                contract,
                action=f"reviewer.attempt_{attempt}",
                observation=review_detail,
            )
            if review_ok:
                return executor_response, session_id, attempt, review_detail, True, contract
            feedback = review_detail

        return executor_response, session_id, self._max_coder_attempts, review_detail, False, contract

    async def _verifier_phase(
        self,
        payload: OrchestrationRunRequest,
        executor_response: str,
    ) -> tuple[bool, str]:
        ok, detail = self._verify(payload.input, executor_response)
        if not ok:
            return False, detail
        if self._tooling is None:
            return ok, detail
        verify_cmd = resolve_verify_command(str(self._tooling.root), "")
        if not verify_cmd:
            return ok, detail + " (no verify command configured)"
        from app.domain.schemas import ExecuteCommandRequest

        try:
            result = await asyncio.to_thread(
                self._tooling.execute_command,
                ExecuteCommandRequest(command=verify_cmd, path=".", dry_run=False, confirmed=True),
            )
            if result.executed and result.exit_code != 0:
                return False, f"Verifier command failed: exit_code={result.exit_code}"
            return True, detail + f" (verify cmd exit_code={result.exit_code})"
        except Exception as exc:  # noqa: BLE001
            return ok, detail + f" (verify cmd skipped: {exc})"

    @staticmethod
    def _build_plan(task_input: str, task_type: TaskType) -> list[str]:
        from app.services.cross_platform_dev_service import CrossPlatformDevService

        if CrossPlatformDevService.is_cross_platform_task(task_input):
            return CrossPlatformDevService().plan_orchestration_steps(task_input, task_type)

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
        action_observation: list[OrchestrationActionObservation],
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
            ]
        )
        if action_observation:
            lines.extend(
                [
                    "OpenHands action/observation:",
                    *[
                        f"- {item.action} => {item.observation[:200]}"
                        for item in action_observation
                    ],
                    "",
                ]
            )
        lines.extend(
            [
                "Task runner report:",
                task_report or "(no task report)",
            ]
        )
        return "\n".join(lines).strip()

    @staticmethod
    def _append_contract_item(
        items: list[OrchestrationActionObservation],
        *,
        action: str,
        observation: str,
    ) -> None:
        items.append(
            OrchestrationActionObservation(
                action=action[:120].strip(),
                observation=observation[:1000].strip() or "(empty)",
            )
        )
