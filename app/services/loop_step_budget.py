from __future__ import annotations

from app.domain.schemas import AgentProfileResponse, AgentRunRequest


def resolve_loop_step_budget(profile: AgentProfileResponse, payload: AgentRunRequest) -> int:
    base = max(1, profile.max_tool_steps or 6)
    text = payload.input.lower()
    if len(payload.input) > 400:
        base += 2
    if any(marker in text for marker in ("refactor", "multi-file", "architecture", "рефактор")):
        base += 2
    if any(marker in text for marker in ("fix", "bug", "test", "исправ", "тест")):
        base += 1
    return max(1, min(base, 20))


def should_escalate_model(*, parse_errors: int, verify_failures: int, repeat_blocks: int) -> bool:
    return parse_errors >= 2 or verify_failures >= 1 or repeat_blocks >= 2
