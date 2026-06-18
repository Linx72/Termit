#!/usr/bin/env python3
"""Backfill normalize_capture_instruction() on existing training_signals.jsonl."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.training_signal_store import TrainingSignalStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize training signal instructions")
    parser.add_argument("--signals-file", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-preserve-full", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    path = args.signals_file.strip() or settings.finetune_training_signals_path
    store = TrainingSignalStore(
        file_path=path,
        min_output_chars=settings.finetune_min_signal_output_chars,
        enabled=True,
    )
    stats = store.normalize_existing_instructions(
        preserve_full=not args.no_preserve_full,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps({"signals_file": path, **stats}, indent=2))
    if args.dry_run:
        print("Dry run — no file changes written.")
    elif stats.get("updated", 0):
        print(f"Updated {stats['updated']} row(s); backup: {path}.bak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
