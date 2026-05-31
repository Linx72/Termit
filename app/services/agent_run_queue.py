from __future__ import annotations

import heapq
import threading
import time
from itertools import count
from queue import Empty, Full
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class AgentRunQueue(Generic[T]):
    """Priority queue: higher `priority` value dequeues first (FIFO within same priority)."""

    def __init__(self, maxsize: int = 100) -> None:
        self._maxsize = max(1, maxsize)
        self._heap: list[tuple[int, int, T]] = []
        self._counter = count()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)

    def qsize(self) -> int:
        with self._lock:
            return len(self._heap)

    def put_nowait(self, item: T, *, priority: int = 0) -> None:
        with self._lock:
            if len(self._heap) >= self._maxsize:
                raise Full
            heapq.heappush(self._heap, (-max(0, priority), next(self._counter), item))
            self._not_empty.notify()

    def get(self, timeout: float | None = 0.5) -> T:
        with self._not_empty:
            if not self._heap:
                if timeout is None:
                    while not self._heap:
                        self._not_empty.wait()
                elif timeout > 0:
                    deadline = time.monotonic() + timeout
                    while not self._heap:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise Empty
                        self._not_empty.wait(remaining)
                else:
                    raise Empty
            _, _, item = heapq.heappop(self._heap)
            return item

    def task_done(self) -> None:
        return
