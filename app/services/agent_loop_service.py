from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

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
from app.services.tool_json_parser import ToolJsonParseError, parse_loop_action

LOOP_SYSTEM_APPENDIX = """
You may use tools to complete the task. Respond with a single JSON object only (no markdown unless inside strings).

Tool call:
{"action":"tool","tool":"list_files|read_file|execute_command|apply_patch|web_automation","arguments":{...}}

Final answer:
{"action":"final","answer":"..."}

apply_patch arguments: path, content OR hunks[{old_text,new_text}], create, dry_run, confirmed.
For execute_command and apply_patch prefer dry_run=true unless execution is explicitly required.
Allowed tools depend on agent configuration.
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
    pass


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
    ) -> AgentLoopResult:
        safe_steps = max(1, min(max_steps, 20))
        memory_block = ""
        if memory_context:
            memory_block = "\n\nLong-term agent memory:\n" + "\n".join(f"- {line}" for line in memory_context)

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

        for step in range(1, safe_steps + 1):
            chat_request = ChatRequest(
                message=payload.input if step == 1 else "Continue with the next tool step or final answer.",
                task_type=profile.task_type,
                model=profile.model,
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
            chat_result = await chat_fn(chat_request)
            last_provider = chat_result.provider
            last_model = chat_result.model
            if chat_result.model not in attempted:
                attempted.append(chat_result.model)

            try:
                action = parse_loop_action(chat_result.response)
            except ToolJsonParseError as exc:
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

            tool_name = str(action.get("tool", "")).strip()
            arguments = action.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            try:
                observation = tool_fn(tool_name, arguments)
            except Exception as exc:  # noqa: BLE001
                observation = f"Tool error ({tool_name}): {exc}"

            step_result = LoopStepResult(
                step=step,
                action="tool",
                tool=tool_name,
                observation=observation[:4000],
            )
            steps.append(step_result)
            if on_step:
                on_step(step_result)

            history.append(ChatMessage(role="assistant", content=chat_result.response))
            history.append(
                ChatMessage(
                    role="user",
                    content=f"Tool observation ({tool_name}):\n{observation}\n\nRespond with next JSON action.",
                )
            )

        raise AgentLoopError(f"Tool loop exceeded max steps ({safe_steps}).")


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
            dry_run=bool(arguments.get("dry_run", True)),
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
