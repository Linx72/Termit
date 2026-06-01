"""Dev-only seed helpers for trajectory SFT and DPO training data."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.services.training_signal_store import TrainingSignalStore

INSTRUCTION = "Fix verify command resolver for agent patch loop"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_training_signals(store: TrainingSignalStore, *, min_pairs: int = 20) -> int:
    """Ensure at least min_pairs DPO-eligible signals exist."""
    existing = store.load_dpo_samples(limit=min_pairs * 4)
    if len(existing) >= min_pairs:
        return 0

    created = 0
    base = len(existing)
    for index in range(base, min_pairs):
        instruction = f"{INSTRUCTION} (seed #{index + 1})"
        store.try_capture_tool_step(
            run_id=f"seed-pos-{index:03d}",
            step=1,
            action="tool",
            tool="apply_patch",
            observation=f"Applied patch #{index + 1}; verify passed via resolve_verify_command.",
            instruction=instruction,
            verified=True,
        )
        store.try_capture_negative_tool_step(
            run_id=f"seed-neg-{index:03d}",
            step=2,
            action="tool",
            tool="apply_patch",
            observation=f"Tool error #{index + 1}: verify failed because cwd was wrong.",
            instruction=instruction,
            reason="verify_failed",
        )
        created += 1
    return created


def _count_completed_runs(sqlite_path: Path) -> int:
    if not sqlite_path.exists():
        return 0
    with sqlite3.connect(sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM agent_runs
            WHERE state = 'completed'
              AND response IS NOT NULL
              AND (error IS NULL OR error = '')
            """
        ).fetchone()
    return int(row[0] if row else 0)


def seed_trajectory_runs(
    agent_run_sqlite_path: str | Path,
    *,
    target_count: int = 50,
) -> int:
    """Insert completed agent runs with tool_loop_trace events for SFT export."""
    db_path = Path(agent_run_sqlite_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    existing = _count_completed_runs(db_path)
    if existing >= target_count:
        return 0

    created = 0
    now = _utc_now()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                input TEXT NOT NULL,
                session_id TEXT,
                provider TEXT,
                model TEXT,
                attempts INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL,
                failure_class TEXT,
                attempted_models TEXT NOT NULL,
                response TEXT NOT NULL,
                error TEXT,
                checkpoint_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                state TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                attempt INTEGER NOT NULL
            )
            """
        )

        for index in range(existing, target_count):
            run_id = f"seed-traj-{index:03d}"
            instruction = f"{INSTRUCTION} trajectory seed #{index + 1}"
            trace = json.dumps(
                {
                    "action": "tool",
                    "tool": "apply_patch",
                    "observation": f"Patch applied successfully for scenario #{index + 1}.",
                    "assistant": '{"action":"tool","tool":"apply_patch"}',
                },
                ensure_ascii=False,
            )
            response = f"Completed fix #{index + 1}: verify command resolves from repo root."
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_runs (
                    run_id, agent_id, agent_name, state, created_at, updated_at,
                    input, session_id, provider, model, attempts, max_attempts,
                    failure_class, attempted_models, response, error, checkpoint_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    "seed-agent",
                    "Seed Agent",
                    "completed",
                    now,
                    now,
                    instruction,
                    None,
                    "ollama",
                    "deepseek-coder",
                    1,
                    1,
                    None,
                    "deepseek-coder",
                    response,
                    None,
                    None,
                ),
            )
            events = [
                ("tool_loop_step", f"step 1 for {run_id}"),
                ("tool_loop_trace", trace),
                ("tool_loop_final", "tool loop finished"),
            ]
            for event_type, message in events:
                conn.execute(
                    """
                    INSERT INTO agent_run_events (
                        run_id, event_type, state, message, timestamp, attempt
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, event_type, "completed", message, now, 1),
                )
            created += 1
        conn.commit()
    return created


def seed_dev_training_data(
    *,
    training_signals_path: str,
    agent_run_sqlite_path: str,
    min_output_chars: int = 8,
    min_dpo_pairs: int = 20,
    min_trajectory_runs: int = 50,
) -> dict[str, int]:
    from app.services.training_signal_store import TrainingSignalStore

    store = TrainingSignalStore(
        file_path=training_signals_path,
        min_output_chars=min_output_chars,
        enabled=True,
    )
    signals_added = seed_training_signals(store, min_pairs=min_dpo_pairs)
    trajectories_added = seed_trajectory_runs(
        agent_run_sqlite_path,
        target_count=min_trajectory_runs,
    )
    return {
        "signals_added": signals_added,
        "trajectories_added": trajectories_added,
        "dpo_samples": len(store.load_dpo_samples(limit=min_dpo_pairs * 2)),
        "trajectory_runs": _count_completed_runs(Path(agent_run_sqlite_path)),
    }
