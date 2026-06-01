#!/usr/bin/env python3
"""Seed dev trajectory runs + DPO signals when stores are below sprint thresholds."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.finetune_dev_seed import seed_dev_training_data


def main() -> int:
    settings = get_settings()
    stats = seed_dev_training_data(
        training_signals_path=settings.finetune_training_signals_path,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        min_output_chars=settings.finetune_min_signal_output_chars,
        min_dpo_pairs=int(__import__("os").getenv("TERMIT_FINETUNE_MIN_DPO_PAIRS", "20")),
        min_trajectory_runs=int(__import__("os").getenv("TERMIT_FINETUNE_MIN_TRAJECTORY_RUNS", "50")),
    )
    print(
        "[finetune_seed_dev_data]",
        f"signals_added={stats['signals_added']}",
        f"trajectories_added={stats['trajectories_added']}",
        f"dpo_samples={stats['dpo_samples']}",
        f"trajectory_runs={stats['trajectory_runs']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
