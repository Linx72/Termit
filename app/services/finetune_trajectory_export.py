from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
from typing import Optional


@dataclass
class TrajectoryExportStats:
    raw_runs: int = 0
    exported: int = 0
    skipped_empty: int = 0
    skipped_short: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "raw_runs": self.raw_runs,
            "exported": self.exported,
            "skipped_empty": self.skipped_empty,
            "skipped_short": self.skipped_short,
        }


def _parse_trace_payload(message: str) -> Optional[dict[str, object]]:
    text = message.strip()
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def events_to_messages(
    *,
    instruction: str,
    events: list[tuple[str, str]],
    final_response: str = "",
    system_prompt: str = "",
) -> list[dict[str, str]]:
    """Build ShareGPT-style messages from agent_run_events."""
    messages: list[dict[str, str]] = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})

    prompt = instruction.strip()
    if prompt:
        messages.append({"role": "user", "content": prompt})

    pending_assistant: Optional[str] = None
    for event_type, message in events:
        trace = _parse_trace_payload(message)
        if trace is not None:
            action = str(trace.get("action", ""))
            tool = str(trace.get("tool", "") or "")
            observation = str(trace.get("observation", "") or "").strip()
            assistant_text = str(trace.get("assistant", "") or "").strip()
            if not assistant_text:
                parts = [f'{{"action":"{action}"']
                if tool:
                    parts.append(f',"tool":"{tool}"')
                parts.append("}")
                assistant_text = "".join(parts)
            messages.append({"role": "assistant", "content": assistant_text})
            if observation:
                messages.append({"role": "user", "content": f"Tool observation ({tool or action}):\n{observation}"})
            continue

        if event_type == "tool_loop_trace":
            continue

        if event_type in {"tool_loop_final", "run_completed"}:
            continue

        if event_type in {"tool_loop_tool", "tool_loop_tool_error", "tool_loop_step", "tool_call"}:
            line = message.strip()
            if line:
                messages.append({"role": "assistant", "content": line})
            continue

        if event_type == "tool_loop_parse_error":
            messages.append({"role": "assistant", "content": f"[parse_error] {message.strip()}"})
            continue

    answer = final_response.strip()
    if answer:
        if pending_assistant:
            messages.append({"role": "assistant", "content": pending_assistant})
            pending_assistant = None
        if not messages or messages[-1].get("role") != "assistant" or messages[-1].get("content") != answer:
            messages.append({"role": "assistant", "content": answer})

    return messages


def messages_to_sft_record(
    messages: list[dict[str, str]],
    *,
    run_id: str = "",
    agent_id: str = "",
    category: str = "agent",
) -> Optional[dict[str, object]]:
    if len(messages) < 2:
        return None
    has_assistant = any(item.get("role") == "assistant" for item in messages)
    has_user = any(item.get("role") == "user" for item in messages)
    if not has_assistant or not has_user:
        return None
    record: dict[str, object] = {
        "messages": messages,
        "source": "agent_run_trajectory",
        "category": category,
    }
    if run_id:
        record["run_id"] = run_id
    if agent_id:
        record["agent_id"] = agent_id
    return record


def load_trajectory_sft_rows(
    agent_run_sqlite_path: Path,
    *,
    limit: int = 200,
    success_only: bool = True,
    min_messages: int = 3,
    system_prompt: str = "",
) -> tuple[list[dict[str, object]], TrajectoryExportStats]:
    stats = TrajectoryExportStats()
    if not agent_run_sqlite_path.exists():
        return [], stats

    rows: list[dict[str, object]] = []
    with closing(sqlite3.connect(agent_run_sqlite_path)) as conn:
        conn.row_factory = sqlite3.Row
        query = """
            SELECT run_id, agent_id, input, response, state, error, failure_class
            FROM agent_runs
        """
        if success_only:
            query += """
            WHERE state = 'completed'
              AND response IS NOT NULL
              AND (error IS NULL OR error = '')
              AND (failure_class IS NULL OR failure_class = '')
            """
        query += " ORDER BY updated_at DESC LIMIT ?"
        try:
            runs = conn.execute(query, (limit,)).fetchall()
        except sqlite3.Error:
            return [], stats

        stats = TrajectoryExportStats(raw_runs=len(runs))
        for run in runs:
            run_id = str(run["run_id"])
            events = conn.execute(
                """
                SELECT event_type, message
                FROM agent_run_events
                WHERE run_id = ?
                ORDER BY id ASC
                LIMIT 120
                """,
                (run_id,),
            ).fetchall()
            event_pairs = [(str(item["event_type"]), str(item["message"])) for item in events]
            messages = events_to_messages(
                instruction=str(run["input"] or ""),
                events=event_pairs,
                final_response=str(run["response"] or ""),
                system_prompt=system_prompt,
            )
            if len(messages) < min_messages:
                stats.skipped_short += 1
                continue
            record = messages_to_sft_record(
                messages,
                run_id=run_id,
                agent_id=str(run["agent_id"] or ""),
            )
            if record is None:
                stats.skipped_empty += 1
                continue
            rows.append(record)
            stats.exported += 1

    return rows, stats


def write_sft_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
