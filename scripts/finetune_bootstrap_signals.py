#!/usr/bin/env python3
"""Seed minimal training signals when store is empty (local dev / bootstrap)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.training_signal_store import TrainingSignalStore

INSTRUCTION = "Fix verify command resolver for agent patch loop"


def main() -> int:
    settings = get_settings()
    store = TrainingSignalStore(
        file_path=settings.finetune_training_signals_path,
        min_output_chars=settings.finetune_min_signal_output_chars,
        enabled=True,
    )
    if store.load_samples(1):
        print("[bootstrap] training signals already present, skip", file=sys.stderr)
        return 0

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
    print(f"[bootstrap] seeded signals at {store.file_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
