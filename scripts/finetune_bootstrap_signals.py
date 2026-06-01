#!/usr/bin/env python3
"""Seed minimal training signals when store is empty (local dev / bootstrap)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.finetune_dev_seed import seed_dev_training_data
from app.services.training_signal_store import TrainingSignalStore

INSTRUCTION = "Fix verify command resolver for agent patch loop"


def main() -> int:
    settings = get_settings()
    store = TrainingSignalStore(
        file_path=settings.finetune_training_signals_path,
        min_output_chars=settings.finetune_min_signal_output_chars,
        enabled=True,
    )
    if not store.load_samples(1):
        store.try_capture_tool_step(
            run_id="bootstrap-positive",
            step=1,
            action="tool",
            tool="apply_patch",
            observation="Applied patch and verify passed with resolve_verify_command.",
            instruction=INSTRUCTION,
            verified=True,
        )
        store.try_capture_negative_tool_step(
            run_id="bootstrap-negative",
            step=2,
            action="tool",
            tool="apply_patch",
            observation="Tool error: verify failed because command was not resolved from project root.",
            instruction=INSTRUCTION,
            reason="verify_failed",
        )
        print(f"[bootstrap] seeded minimal signals at {store.file_path}")

    stats = seed_dev_training_data(
        training_signals_path=settings.finetune_training_signals_path,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        min_output_chars=settings.finetune_min_signal_output_chars,
    )
    print(
        "[bootstrap] dev seed",
        f"signals_added={stats['signals_added']}",
        f"trajectories_added={stats['trajectories_added']}",
        f"dpo_samples={stats['dpo_samples']}",
        f"trajectory_runs={stats['trajectory_runs']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
