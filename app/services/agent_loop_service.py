from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from app.domain.schemas import (
    AgentProfileResponse,
    AgentRunRequest,
    ApplyPatchHunk,
    ApplyPatchRequest,
    ChatMessage,
    ChatRequest,
    ExecuteCommandRequest,
    ListFilesRequest,
    ReadFileRequest,
    WebAutomationRequest,
)
from app.services.loop_step_budget import should_escalate_model
from app.services.tool_json_parser import ToolJsonParseError, parse_loop_action

LOOP_SYSTEM_APPENDIX = """
You may use tools to complete the task. Respond with a single JSON object only (no markdown unless inside strings).

Tool call:
{"action":"tool","tool":"list_files|read_file|execute_command|apply_patch|web_automation","arguments":{...}}

Final answer:
{"action":"final","answer":"..."}

Examples (follow this shape exactly):
{"action":"tool","tool":"list_files","arguments":{"path":".","pattern":"*.py"}}
{"action":"tool","tool":"read_file","arguments":{"path":"app/main.py"}}
{"action":"tool","tool":"apply_patch","arguments":{"path":"app/main.py","hunks":[{"old_text":"old","new_text":"new"}],"confirmed":true}}
{"action":"final","answer":"Fixed the handler; tests should pass."}

apply_patch arguments: path, content OR hunks[{old_text,new_text}], create, dry_run, confirmed.
For execute_command and apply_patch use confirmed=true when applying real changes.
Allowed tools depend on agent configuration.
If verify tests fail after a patch, fix the code and retry apply_patch.
"""


@dataclass(frozen=True)
class LoopStepResult:
    step: int
    action: str
    tool: Optional[str]
    observation: str


@dataclass(frozen=True)
class AgentLoopResult:
    response: str
    steps: list[LoopStepResult]
    provider: str
    model: str
    attempted_models: list[str]


class AgentLoopError(Exception):
    def __init__(self, message: str, checkpoint: dict[str, object] | None = None) -> None:
        self.checkpoint = checkpoint
        super().__init__(message)


class AgentAwaitingConfirmation(AgentLoopError):
    def __init__(self, checkpoint: dict[str, object]) -> None:
        super().__init__("Awaiting user confirmation for risky tool.", checkpoint)


def _tool_fingerprint(tool_name: str, arguments: dict[str, object]) -> str:
    return json.dumps({"tool": tool_name, "arguments": arguments}, sort_keys=True, ensure_ascii=True)


def _observation_flags(observation: str) -> dict[str, object]:
    try:
        data = json.loads(observation)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    flags: dict[str, object] = {}
    if data.get("requires_confirmation"):
        flags["requires_confirmation"] = True
    verify = data.get("verify")
    if isinstance(verify, dict) and verify.get("executed") and int(verify.get("exit_code") or 0) != 0:
        flags["verify_failed"] = True
    return flags


def _serialize_history(history: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in history]


def _deserialize_history(items: list[object]) -> list[ChatMessage]:
    restored: list[ChatMessage] = []
    for item in items:
        if isinstance(item, dict):
            restored.append(
                ChatMessage(role=str(item.get("role", "user")), content=str(item.get("content", "")))
            )
    return restored


class AgentLoopService:
    async def run(
        self,
        *,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
        chat_fn,
        tool_fn: Callable[[str, dict[str, object]], str],
        memory_context: list[str],
        max_steps: int,
        on_step: Optional[Callable[[LoopStepResult], None]] = None,
        resume_checkpoint: Optional[dict[str, object]] = None,
        native_chat_fn: Optional[Callable[[ChatRequest], Awaitable[object]]] = None,
        verify_fn: Optional[Callable[[], tuple[bool, str]]] = None,
        escalation_models: Optional[list[str]] = None,
    ) -> AgentLoopResult:
        safe_steps = max(1, min(max_steps, 20))
        memory_block = ""
        if memory_context:
            memory_block = "\n\nLong-term agent memory:\n" + "\n".join(f"- {line}" for line in memory_context)

        if resume_checkpoint:
            history = _deserialize_history(list(resume_checkpoint.get("history", [])))
            if not history:
                history = [
                    ChatMessage(
                        role="system",
                        content=profile.system_prompt + LOOP_SYSTEM_APPENDIX + memory_block,
                    ),
                    ChatMessage(role="user", content=payload.input),
                ]
        else:
            history = [
                ChatMessage(
                    role="system",
                    content=profile.system_prompt + LOOP_SYSTEM_APPENDIX + memory_block,
                ),
                ChatMessage(role="user", content=payload.input),
            ]

        steps: list[LoopStepResult] = []
        last_provider = "unknown"
        last_model = profile.model or "default"
        attempted: list[str] = []
        seen_tools: set[str] = set()
        start_step = 1
        parse_errors = 0
        verify_failures = 0
        repeat_blocks = 0
        active_model = profile.model
        escalation = list(escalation_models or [])

        def _checkpoint(step: int) -> dict[str, object]:
            return {
                "history": _serialize_history(history),
                "step": step,
                "active_model": active_model,
            }

        def _maybe_escalate() -> None:
            nonlocal active_model
            if not escalation or not should_escalate_model(
                parse_errors=parse_errors,
                verify_failures=verify_failures,
                repeat_blocks=repeat_blocks,
            ):
                return
            for candidate in escalation:
                if candidate and candidate != active_model:
                    active_model = candidate
                    break

        async def _finalize(step: int, answer: str) -> AgentLoopResult:
            if verify_fn is not None:
                ok, detail = verify_fn()
                step_result = LoopStepResult(
                    step=step,
                    action="verify_pass" if ok else "verify_failed",
                    tool=None,
                    observation=detail[:4000],
                )
                steps.append(step_result)
                if on_step:
                    on_step(step_result)
                if not ok:
                    nonlocal verify_failures
                    verify_failures += 1
                    _maybe_escalate()
                    history.append(ChatMessage(role="assistant", content=answer))
                    history.append(
                        ChatMessage(
                            role="user",
                            content=(
                                f"Final verify failed:\n{detail}\n\n"
                                "Fix issues and continue with tools or a corrected final answer."
                            ),
                        )
                    )
                    raise AgentLoopError("Verify phase failed before final answer.", _checkpoint(step))
            step_result = LoopStepResult(step=step, action="final", tool=None, observation=answer[:500])
            steps.append(step_result)
            if on_step:
                on_step(step_result)
            return AgentLoopResult(
                response=answer,
                steps=steps,
                provider=last_provider,
                model=last_model,
                attempted_models=attempted or [last_model],
            )

        async def _handle_tool(step: int, tool_name: str, arguments: dict[str, object], assistant_text: str) -> None:
            nonlocal verify_failures
            fingerprint = _tool_fingerprint(tool_name, arguments)
            if fingerprint in seen_tools:
                nonlocal repeat_blocks
                repeat_blocks += 1
                _maybe_escalate()
                observation = (
                    f"Repeat tool call detected for {tool_name}. "
                    "Use a different action or provide the final answer."
                )
                step_result = LoopStepResult(
                    step=step,
                    action="repeat_blocked",
                    tool=tool_name,
                    observation=observation,
                )
                steps.append(step_result)
                if on_step:
                    on_step(step_result)
                history.append(ChatMessage(role="assistant", content=assistant_text))
                history.append(
                    ChatMessage(role="user", content=f"{observation}\n\nRespond with next action.")
                )
                return
            seen_tools.add(fingerprint)
            try:
                observation = tool_fn(tool_name, arguments)
            except Exception as exc:  # noqa: BLE001
                observation = f"Tool error ({tool_name}): {exc}"
            flags = _observation_flags(observation)
            if flags.get("requires_confirmation"):
                history.append(ChatMessage(role="assistant", content=assistant_text))
                raise AgentAwaitingConfirmation(
                    {
                        "history": _serialize_history(history),
                        "pending_tool": tool_name,
                        "pending_arguments": arguments,
                        "step": step,
                        "active_model": active_model,
                    }
                )
            step_result = LoopStepResult(
                step=step,
                action="tool",
                tool=tool_name,
                observation=observation[:4000],
            )
            steps.append(step_result)
            if on_step:
                on_step(step_result)
            history.append(ChatMessage(role="assistant", content=assistant_text))
            user_note = f"Tool observation ({tool_name}):\n{observation}\n\nRespond with next action."
            if flags.get("verify_failed"):
                verify_failures += 1
                _maybe_escalate()
                user_note = (
                    f"Patch verify failed.\n{observation}\n\n"
                    "Fix the issue and respond with the next tool action or final answer."
                )
            history.append(ChatMessage(role="user", content=user_note))

        if resume_checkpoint and resume_checkpoint.get("pending_tool"):
            pending_tool = str(resume_checkpoint.get("pending_tool", "")).strip()
            pending_args = resume_checkpoint.get("pending_arguments", {})
            if not isinstance(pending_args, dict):
                pending_args = {}
            start_step = int(resume_checkpoint.get("step", 1))
            active_model = str(resume_checkpoint.get("active_model") or active_model or profile.model or "default")
            observation = tool_fn(pending_tool, pending_args)
            flags = _observation_flags(observation)
            if flags.get("requires_confirmation"):
                raise AgentAwaitingConfirmation(
                    {
                        "history": _serialize_history(history),
                        "pending_tool": pending_tool,
                        "pending_arguments": pending_args,
                        "step": start_step,
                    }
                )
            step_result = LoopStepResult(
                step=start_step,
                action="tool",
                tool=pending_tool,
                observation=observation[:4000],
            )
            steps.append(step_result)
            if on_step:
                on_step(step_result)
            history.append(
                ChatMessage(
                    role="assistant",
                    content=json.dumps(
                        {"action": "tool", "tool": pending_tool, "arguments": pending_args},
                        ensure_ascii=True,
                    ),
                )
            )
            user_note = f"Tool observation ({pending_tool}):\n{observation}\n\nRespond with next JSON action."
            if flags.get("verify_failed"):
                user_note = (
                    f"Patch verify failed.\n{observation}\n\n"
                    "Fix the issue and respond with the next JSON tool action or final answer."
                )
            history.append(ChatMessage(role="user", content=user_note))
            start_step += 1

        for step in range(start_step, safe_steps + 1):
            continuation = (
                payload.input
                if step == 1 and start_step == 1
                else "Continue with the next tool step or final answer."
            )
            chat_request = ChatRequest(
                message=continuation,
                task_type=profile.task_type,
                model=active_model,
                session_id=payload.session_id,
                use_memory=False,
                use_retrieval=profile.use_retrieval if payload.use_retrieval is None else payload.use_retrieval,
                retrieval_limit=payload.retrieval_limit
                if payload.retrieval_limit is not None
                else profile.retrieval_limit,
                retrieval_path_prefix=payload.retrieval_path_prefix
                if payload.retrieval_path_prefix is not None
                else profile.retrieval_path_prefix,
                temperature=payload.temperature if payload.temperature is not None else profile.temperature,
                max_tokens=payload.max_tokens if payload.max_tokens is not None else profile.max_tokens,
                history=list(history),
            )

            if native_chat_fn is not None and active_model and str(active_model).startswith("openai_compat:"):
                native_result = await native_chat_fn(chat_request)
                last_provider = native_result.provider
                last_model = native_result.model
                for model_name in native_result.attempted_models:
                    if model_name not in attempted:
                        attempted.append(model_name)
                if native_result.tool_calls:
                    tool_call = native_result.tool_calls[0]
                    assistant_text = json.dumps(
                        {
                            "action": "tool",
                            "tool": tool_call.name,
                            "arguments": tool_call.arguments,
                        },
                        ensure_ascii=True,
                    )
                    await _handle_tool(step, tool_call.name, tool_call.arguments, assistant_text)
                    continue
                if native_result.content.strip():
                    return await _finalize(step, native_result.content.strip())

            chat_result = await chat_fn(chat_request)
            last_provider = chat_result.provider
            last_model = chat_result.model
            if chat_result.model not in attempted:
                attempted.append(chat_result.model)

            try:
                action = parse_loop_action(chat_result.response)
            except ToolJsonParseError as exc:
                parse_errors += 1
                _maybe_escalate()
                observation = f"Tool parse error: {exc}"
                step_result = LoopStepResult(step=step, action="parse_error", tool=None, observation=observation)
                steps.append(step_result)
                if on_step:
                    on_step(step_result)
                history.append(ChatMessage(role="assistant", content=chat_result.response))
                history.append(
                    ChatMessage(
                        role="user",
                        content=(
                            f"{observation}\n\nRespond with valid JSON: "
                            '{"action":"tool","tool":"...","arguments":{...}} or {"action":"final","answer":"..."}.'
                        ),
                    )
                )
                continue
            if action.get("action") == "final":
                answer = str(action.get("answer", chat_result.response))
                return await _finalize(step, answer)

            tool_name = str(action.get("tool", "")).strip()
            arguments = action.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            await _handle_tool(step, tool_name, arguments, chat_result.response)

        raise AgentLoopError(
            f"Tool loop exceeded max steps ({safe_steps}).",
            checkpoint=_checkpoint(safe_steps),
        )


def build_tool_arguments(tool_name: str, arguments: dict[str, object]):
    if tool_name == "list_files":
        return ListFilesRequest(
            path=str(arguments.get("path", ".")),
            pattern=str(arguments.get("pattern", "*")),
        )
    if tool_name == "read_file":
        return ReadFileRequest(
            path=str(arguments.get("path", ".")),
            file=str(arguments.get("file", "")),
        )
    if tool_name == "execute_command":
        return ExecuteCommandRequest(
            command=str(arguments.get("command", "echo ok")),
            path=str(arguments.get("path", ".")),
            dry_run=bool(arguments.get("dry_run", True)),
            confirmed=bool(arguments.get("confirmed", False)),
        )
    if tool_name == "apply_patch":
        hunks_raw = arguments.get("hunks", [])
        hunks = []
        if isinstance(hunks_raw, list):
            for item in hunks_raw:
                if isinstance(item, dict):
                    hunks.append(
                        ApplyPatchHunk(
                            old_text=str(item.get("old_text", "")),
                            new_text=str(item.get("new_text", "")),
                        )
                    )
        content = arguments.get("content")
        return ApplyPatchRequest(
            path=str(arguments.get("path", "")),
            hunks=hunks,
            content=str(content) if content is not None else None,
            create=bool(arguments.get("create", False)),
            dry_run=bool(arguments.get("dry_run", False)),
            confirmed=bool(arguments.get("confirmed", False)),
        )
    if tool_name == "web_automation":
        return WebAutomationRequest(
            url=str(arguments.get("url", "")),
            objective=str(arguments.get("objective", "Collect evidence")),
            max_steps=int(arguments.get("max_steps", 4)),
            timeout_seconds=int(arguments.get("timeout_seconds", 10)),
            capture_links_limit=int(arguments.get("capture_links_limit", 10)),
        )
    raise ValueError(f"Unsupported tool: {tool_name}")
