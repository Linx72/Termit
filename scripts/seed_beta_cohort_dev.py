#!/usr/bin/env python3
"""Синтетическая beta-когорта для локальной отладки D30 retention (только dev)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.beta_cohort_service import BetaCohortService
from app.services.feedback_store import FeedbackStore


def _utc_day_offset(days: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days)
    return moment.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()


def seed_feedback_lines(path: Path, actors: int, retained_ratio: float) -> int:
    """Писать JSONL с контролируемыми датами first touch и D30 retention."""
    path.parent.mkdir(parents=True, exist_ok=True)
    retained_count = int(round(actors * retained_ratio))
    lines: list[str] = []
    for index in range(actors):
        session_id = f"beta-dev-seed-{index:02d}"
        first_day_offset = 40 + index
        lines.append(
            json.dumps(
                {
                    "timestamp": _utc_day_offset(first_day_offset),
                    "message": f"beta dev seed cohort actor {index}",
                    "rating": 5,
                    "contact": None,
                    "api_key": None,
                    "session_id": session_id,
                },
                ensure_ascii=True,
            )
        )
        if index < retained_count:
            lines.append(
                json.dumps(
                    {
                        "timestamp": _utc_day_offset(first_day_offset - 5),
                        "message": f"beta dev seed retained {index}",
                        "rating": 5,
                        "contact": None,
                        "api_key": None,
                        "session_id": session_id,
                    },
                    ensure_ascii=True,
                )
            )
    with path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")
    return len(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic beta cohort (dev only)")
    parser.add_argument("--actors", type=int, default=6, help="Число synthetic actors (≥5 для D30 gate)")
    parser.add_argument("--retained-ratio", type=float, default=0.67, help="Доля retained в eligible cohort")
    parser.add_argument("--force", action="store_true", help="Без TERMIT_BETA_DEV_SEED=true")
    args = parser.parse_args()

    if not args.force and os.getenv("TERMIT_BETA_DEV_SEED", "").lower() not in {"1", "true", "yes"}:
        print(
            "Отказ: задайте TERMIT_BETA_DEV_SEED=true или --force (только local dev).",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    path = Path(settings.feedback_file_path)
    written = seed_feedback_lines(path, max(5, args.actors), args.retained_ratio)

    store = FeedbackStore(file_path=str(path))
    service = BetaCohortService(
        feedback_entries_provider=store.list_entries,
        task_activity_provider=lambda: [],
        run_activity_provider=lambda: [],
    )
    metrics = service.build_metrics()
    meta_path = Path(os.getenv("TERMIT_BETA_COHORT_META", str(ROOT / "data" / "beta_cohort_meta.json")))
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(
            {
                "dev_only": True,
                "seeded_at": datetime.now(timezone.utc).isoformat(),
                "actors": max(5, args.actors),
                "retained_ratio": args.retained_ratio,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"OK — добавлено {written} feedback строк в {path}")
    print(f"OK — meta dev seed → {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
