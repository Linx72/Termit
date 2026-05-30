from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Optional, Protocol

from app.domain.schemas import AgentRunEvent, AgentRunRecordResponse, AgentRunState


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

    def cleanup_old_runs(
        self,
        cutoff_iso: str,
        terminal_states: set[AgentRunState],
        dry_run: bool = False,
    ) -> tuple[int, int]:
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
