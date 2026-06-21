from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional, Protocol

from app.domain.schemas import AgentRunEvent, AgentRunRecordResponse, AgentRunState
from app.services.tool_loop_metrics import (
    aggregate_tool_loop_events,
    classify_tool_loop_event,
    empty_tool_loop_metrics,
)
from app.services.mcp_usage_metrics import aggregate_mcp_usage_events, empty_mcp_usage_metrics


class AgentRunStore(Protocol):
    def put_run(self, run: AgentRunRecordResponse) -> None:
        ...

    def get_run(self, run_id: str) -> Optional[AgentRunRecordResponse]:
        ...

    def list_runs(self, limit: int = 50) -> list[AgentRunRecordResponse]:
        ...

    def list_runs_by_agent(self, agent_id: str, limit: int = 50) -> list[AgentRunRecordResponse]:
        ...

    def append_event(self, run_id: str, event: AgentRunEvent) -> None:
        ...

    def get_events(self, run_id: str, limit: int = 500) -> list[AgentRunEvent]:
        ...

    def trim_events(self, run_id: str, max_events: int) -> int:
        ...

    def count_runs(self) -> int:
        ...

    def count_runs_by_state(self) -> dict[str, int]:
        ...

    def tool_loop_event_metrics(
        self,
        recent_days: int | None = None,
        recent_run_limit: int | None = None,
    ) -> dict[str, object]:
        ...

    def mcp_usage_metrics(self) -> dict[str, object]:
        ...

    def cleanup_old_runs(
        self,
        cutoff_iso: str,
        terminal_states: set[AgentRunState],
        dry_run: bool = False,
    ) -> tuple[int, int]:
        ...

    def set_lifecycle_status(self, run_id: str, lifecycle_status: str) -> bool:
        ...

    def list_all_runs(self, limit: int = 100, lifecycle_status: str | None = None) -> list[AgentRunRecordResponse]:
        ...


class InMemoryAgentRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, AgentRunRecordResponse] = {}
        self._events: dict[str, list[AgentRunEvent]] = {}
        self._lock = Lock()

    def put_run(self, run: AgentRunRecordResponse) -> None:
        with self._lock:
            self._runs[run.run_id] = AgentRunRecordResponse.model_validate(run.model_dump())
            self._events.setdefault(run.run_id, [])

    def get_run(self, run_id: str) -> Optional[AgentRunRecordResponse]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            return AgentRunRecordResponse.model_validate(run.model_dump())

    def list_runs(self, limit: int = 50) -> list[AgentRunRecordResponse]:
        with self._lock:
            runs = list(self._runs.values())
        runs.sort(key=lambda item: item.updated_at, reverse=True)
        return [AgentRunRecordResponse.model_validate(item.model_dump()) for item in runs[:limit]]

    def list_runs_by_agent(self, agent_id: str, limit: int = 50) -> list[AgentRunRecordResponse]:
        with self._lock:
            runs = [item for item in self._runs.values() if item.agent_id == agent_id]
        runs.sort(key=lambda item: item.updated_at, reverse=True)
        return [AgentRunRecordResponse.model_validate(item.model_dump()) for item in runs[:limit]]

    def append_event(self, run_id: str, event: AgentRunEvent) -> None:
        with self._lock:
            self._events.setdefault(run_id, []).append(AgentRunEvent.model_validate(event.model_dump()))

    def get_events(self, run_id: str, limit: int = 500) -> list[AgentRunEvent]:
        safe_limit = max(1, min(limit, 2000))
        with self._lock:
            events = list(self._events.get(run_id, []))
        return [AgentRunEvent.model_validate(item.model_dump()) for item in events[-safe_limit:]]

    def trim_events(self, run_id: str, max_events: int) -> int:
        safe_max = max(1, max_events)
        with self._lock:
            events = self._events.get(run_id, [])
            if len(events) <= safe_max:
                return 0
            deleted = len(events) - safe_max
            self._events[run_id] = events[-safe_max:]
            return deleted

    def count_runs(self) -> int:
        with self._lock:
            return len(self._runs)

    def count_runs_by_state(self) -> dict[str, int]:
        with self._lock:
            runs = list(self._runs.values())
        counts: dict[str, int] = {}
        for run in runs:
            key = run.state.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def tool_loop_event_metrics(
        self,
        recent_days: int | None = None,
        recent_run_limit: int | None = None,
    ) -> dict[str, object]:
        cutoff: datetime | None = None
        if recent_days is not None and recent_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
        recent_run_ids: set[str] | None = None
        if recent_run_limit is not None and recent_run_limit > 0:
            with self._lock:
                last_ts: dict[str, datetime] = {}
                for run_id, events in self._events.items():
                    for event in events:
                        if classify_tool_loop_event(event.event_type, event.message) is None:
                            continue
                        try:
                            event_dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                        prev = last_ts.get(run_id)
                        if prev is None or event_dt > prev:
                            last_ts[run_id] = event_dt
                ordered = sorted(last_ts.items(), key=lambda item: item[1], reverse=True)
                recent_run_ids = {run_id for run_id, _ in ordered[:recent_run_limit]}
        with self._lock:
            rows: list[tuple[str, str, str]] = []
            completed_run_ids: set[str] = set()
            for run_id, events in self._events.items():
                if recent_run_ids is not None and run_id not in recent_run_ids:
                    continue
                run = self._runs.get(run_id)
                if run and run.state == AgentRunState.completed:
                    completed_run_ids.add(run_id)
                for event in events:
                    if cutoff is not None:
                        try:
                            event_dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
                            if event_dt < cutoff:
                                continue
                        except ValueError:
                            continue
                    rows.append((run_id, event.event_type, event.message))
        if not rows:
            return empty_tool_loop_metrics()
        return aggregate_tool_loop_events(rows, completed_run_ids)

    def mcp_usage_metrics(self) -> dict[str, object]:
        with self._lock:
            rows: list[tuple[str, str, str]] = []
            for run_id, events in self._events.items():
                for event in events:
                    rows.append((run_id, event.event_type, event.message))
        if not rows:
            return empty_mcp_usage_metrics()
        return aggregate_mcp_usage_events(rows)

    def cleanup_old_runs(
        self,
        cutoff_iso: str,
        terminal_states: set[AgentRunState],
        dry_run: bool = False,
    ) -> tuple[int, int]:
        try:
            cutoff_dt = datetime.fromisoformat(cutoff_iso)
        except ValueError:
            return (0, 0)
        deleted_runs = 0
        deleted_events = 0
        with self._lock:
            to_delete: list[str] = []
            for run_id, run in self._runs.items():
                if run.state not in terminal_states:
                    continue
                try:
                    updated = datetime.fromisoformat(run.updated_at)
                except ValueError:
                    continue
                if updated < cutoff_dt:
                    to_delete.append(run_id)

            deleted_runs = len(to_delete)
            for run_id in to_delete:
                deleted_events += len(self._events.get(run_id, []))
                if not dry_run:
                    self._runs.pop(run_id, None)
                    self._events.pop(run_id, None)
        return deleted_runs, deleted_events

    def set_lifecycle_status(self, run_id: str, lifecycle_status: str) -> bool:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return False
            run.lifecycle_status = lifecycle_status
            from datetime import datetime, timezone
            run.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            return True

    def list_all_runs(self, limit: int = 100, lifecycle_status: str | None = None) -> list[AgentRunRecordResponse]:
        with self._lock:
            runs = list(self._runs.values())
        if lifecycle_status:
            runs = [r for r in runs if getattr(r, 'lifecycle_status', 'active') == lifecycle_status]
        runs.sort(key=lambda item: item.updated_at, reverse=True)
        return [AgentRunRecordResponse.model_validate(item.model_dump()) for item in runs[:limit]]
