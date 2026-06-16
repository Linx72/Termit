"""Beta cohort retention metrics from feedback, tasks, and agent runs."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional


def _parse_day(value: str) -> Optional[date]:
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def _actor_from_feedback(entry: dict[str, object]) -> str:
    api_key = entry.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
        return f"key:{digest}"
    session_id = entry.get("session_id")
    if isinstance(session_id, str) and session_id.strip():
        return f"sess:{session_id.strip()}"
    return "anon"


class BetaCohortService:
    def __init__(
        self,
        *,
        feedback_entries_provider: Callable[[], list[dict[str, object]]],
        task_activity_provider: Callable[[], list[tuple[str, str]]],
        run_activity_provider: Callable[[], list[tuple[str, str]]],
        target_d30_retention: float = 0.35,
    ) -> None:
        self._feedback_entries = feedback_entries_provider
        self._task_activity = task_activity_provider
        self._run_activity = run_activity_provider
        self._target_d30 = max(0.0, min(target_d30_retention, 1.0))

    def _collect_activity(self) -> dict[str, set[date]]:
        activities: dict[str, set[date]] = defaultdict(set)
        for entry in self._feedback_entries():
            day = _parse_day(str(entry.get("timestamp", "")))
            if day is None:
                continue
            activities[_actor_from_feedback(entry)].add(day)
        for actor_key, timestamp in self._task_activity():
            day = _parse_day(timestamp)
            if day is None:
                continue
            actor = actor_key.strip() or "task:unknown"
            if not actor.startswith(("sess:", "key:", "run:", "task:")):
                actor = f"sess:{actor}"
            activities[actor].add(day)
        for actor_key, timestamp in self._run_activity():
            day = _parse_day(timestamp)
            if day is None:
                continue
            actor = actor_key.strip() or "run:unknown"
            if not actor.startswith(("sess:", "key:", "run:", "task:")):
                actor = f"run:{actor[:12]}"
            activities[actor].add(day)
        return activities

    @staticmethod
    def _retention_for_window(
        activities: dict[str, set[date]],
        *,
        window_days: int,
        today: date,
    ) -> tuple[Optional[float], int, int]:
        eligible = 0
        retained = 0
        for dates in activities.values():
            if not dates:
                continue
            first = min(dates)
            if (today - first).days < window_days:
                continue
            eligible += 1
            end = first + timedelta(days=window_days)
            if any(first < active_day <= end for active_day in dates):
                retained += 1
        if eligible == 0:
            return None, 0, 0
        return round(retained / eligible, 4), eligible, retained

    def build_metrics(self) -> dict[str, object]:
        today = datetime.now(timezone.utc).date()
        activities = self._collect_activity()
        d30_rate, d30_cohort, d30_retained = self._retention_for_window(
            activities, window_days=30, today=today
        )
        d7_rate, d7_cohort, d7_retained = self._retention_for_window(
            activities, window_days=7, today=today
        )
        week_ago = today - timedelta(days=7)
        active_users_7d = sum(1 for dates in activities.values() if any(day >= week_ago for day in dates))
        return {
            "d30_retention_rate": d30_rate,
            "cohort_size_d30": d30_cohort,
            "retained_d30": d30_retained,
            "d7_retention_rate": d7_rate,
            "cohort_size_d7": d7_cohort,
            "retained_d7": d7_retained,
            "active_users_7d": active_users_7d,
            "tracked_actors": len(activities),
            "target_d30_retention": self._target_d30,
        }
