from collections import defaultdict
from threading import Lock
from typing import Protocol

from app.domain.schemas import ChatMessage


class MemoryBackend(Protocol):
    def append(self, session_id: str, message: ChatMessage) -> None:
        ...

    def get(self, session_id: str) -> list[ChatMessage]:
        ...

    def clear(self, session_id: str) -> bool:
        ...


class MemoryStore:
    def __init__(self, max_messages_per_session: int = 40) -> None:
        self.max_messages_per_session = max_messages_per_session
        self._sessions: dict[str, list[ChatMessage]] = defaultdict(list)
        self._lock = Lock()

    def append(self, session_id: str, message: ChatMessage) -> None:
        with self._lock:
            history = self._sessions[session_id]
            history.append(message)
            if len(history) > self.max_messages_per_session:
                self._sessions[session_id] = history[-self.max_messages_per_session :]

    def get(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def clear(self, session_id: str) -> bool:
        with self._lock:
            if session_id not in self._sessions:
                return False
            del self._sessions[session_id]
            return True
