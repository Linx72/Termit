#!/usr/bin/env python3
"""Seed minimal completed agent runs with tool_loop_trace events (local dev fallback)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.domain.schemas import AgentRunEvent, AgentRunRecordResponse, AgentRunState
from app.services.finetune_trajectory_export import load_trajectory_sft_rows
from app.services.sqlite_agent_run_store import SQLiteAgentRunStore

INSTRUCTION = "Fix verify command resolver for agent patch loop"
RESPONSE = "Updated resolve_verify_command to use project root from repo map."


def _trace_message(*, action: str, tool: str, observation: str) -> str:
    return json.dumps(
        {"action": action, "tool": tool, "observation": observation},
        ensure_ascii=True,
    )


def main() -> int:
    settings = get_settings()
    db_path = settings.agent_run_sqlite_path
    store = SQLiteAgentRunStore(db_path)

    rows, stats = load_trajectory_sft_rows(
        Path(db_path),
        limit=200,
        success_only=True,
        min_messages=3,
    )
    if stats.exported >= 10:
        print(f"[bootstrap] trajectory runs already present ({stats.exported} exportable), skip")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    target = max(12, 12 - stats.exported)
    for index in range(target):
        run_id = f"bootstrap-traj-{uuid4().hex[:10]}"
        agent_id = f"bootstrap-agent-{index % 3}"
        run = AgentRunRecordResponse(
            run_id=run_id,
            agent_id=agent_id,
            agent_name="Bootstrap Eval Agent",
            state=AgentRunState.completed,
            created_at=now,
            updated_at=now,
            input=INSTRUCTION,
            provider="bootstrap",
            model="ollama:qwen2.5-coder",
            attempts=1,
            max_attempts=1,
            attempted_models=["ollama:qwen2.5-coder"],
            response=RESPONSE,
        )
        store.put_run(run)
        events = [
            AgentRunEvent(
                event_type="tool_loop_trace",
                state=AgentRunState.running,
                message=_trace_message(
                    action="tool",
                    tool="read_file",
                    observation="Read app/services/verify_command_resolver.py",
                ),
                timestamp=now,
                attempt=1,
            ),
            AgentRunEvent(
                event_type="tool_loop_trace",
                state=AgentRunState.running,
                message=_trace_message(
                    action="tool",
                    tool="apply_patch",
                    observation="Applied patch; verify passed with pytest.",
                ),
                timestamp=now,
                attempt=1,
            ),
            AgentRunEvent(
                event_type="run_completed",
                state=AgentRunState.completed,
                message=RESPONSE,
                timestamp=now,
                attempt=1,
            ),
        ]
        for event in events:
            store.append_event(run_id, event)

    rows_after, stats_after = load_trajectory_sft_rows(
        Path(db_path),
        limit=200,
        success_only=True,
        min_messages=3,
    )
    print(
        f"[bootstrap] seeded trajectory runs at {db_path} "
        f"(exportable={stats_after.exported}, added~{target})"
    )
    if stats_after.exported < 10:
        print("[bootstrap] warning: exportable samples still below 10", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
