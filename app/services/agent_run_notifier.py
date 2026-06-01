from __future__ import annotations

import asyncio
from threading import Lock
from typing import Any


class AgentRunNotifier:
    """In-memory pub/sub for agent run SSE subscribers."""

    _instance: AgentRunNotifier | None = None

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: dict[str, list[asyncio.Queue[tuple[str, dict[str, Any]]]]] = {}

    @classmethod
    def get(cls) -> AgentRunNotifier:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, run_id: str) -> asyncio.Queue[tuple[str, dict[str, Any]]]:
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[tuple[str, dict[str, Any]]]) -> None:
        with self._lock:
            subs = self._subscribers.get(run_id, [])
            if queue in subs:
                subs.remove(queue)
            if not subs:
                self._subscribers.pop(run_id, None)

    def publish(self, run_id: str, kind: str, payload: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers.get(run_id, []))
        for queue in subs:
            try:
                queue.put_nowait((kind, payload))
            except asyncio.QueueFull:
                pass
