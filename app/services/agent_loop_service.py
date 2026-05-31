from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Optional

from app.domain.schemas import (
    AgentProfileResponse,
    AgentRunRequest,
    ChatMessage,
    ChatRequest,
    ExecuteCommandRequest,
    ListFilesRequest,
    ReadFileRequest,
    WebAutomationRequest,
)

LOOP_SYSTEM_APPENDIX = """
You may use tools to complete the task. Respond with a single JSON object only (no markdown unless inside strings).

Tool call:
{"action":"tool","tool":"list_files|read_file|execute_command|web_automation","arguments":{...}}

Final answer:
{"action":"final","answer":"..."}

Allowed tools depend on agent configuration. For execute_command prefer dry_run=true unless execution is explicitly required.
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


def extract_json_object(text: str) -> Optional[dict[str, object]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(payload, dict):
        return payload
    return None


def parse_loop_action(text: str) -> dict[str, object]:
    payload = extract_json_object(text)
    if payload is None:
        return {"action": "final", "answer": text.strip()}
    action = str(payload.get("action", "final")).lower()
    if action == "tool":
        return {
            "action": "tool",
            "tool": str(payload.get("tool", "")).strip(),
            "arguments": payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {},
        }
    return {"action": "final", "answer": str(payload.get("answer", text)).strip()}


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

            action = parse_loop_action(chat_result.response)
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
    if tool_name == "web_automation":
        return WebAutomationRequest(
            url=str(arguments.get("url", "")),
            objective=str(arguments.get("objective", "Collect evidence")),
            max_steps=int(arguments.get("max_steps", 4)),
            timeout_seconds=int(arguments.get("timeout_seconds", 10)),
            capture_links_limit=int(arguments.get("capture_links_limit", 10)),
        )
    raise ValueError(f"Unsupported tool: {tool_name}")
