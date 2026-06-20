"""Кэш стабильных prefix-блоков для agent run (repo map, packing, rules).

Снижает повторную сборку контекста при одинаковых workspace/query/changed_files.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class AgentPromptCacheService:
    """In-memory TTL-кэш строк контекста для agent runs."""

    ttl_seconds: int = 300
    _entries: dict[str, tuple[float, list[str]]] = field(default_factory=dict)

    @staticmethod
    def enrichment_key(
        *,
        agent_id: str,
        path_prefix: str,
        instruction: str,
        changed_files: list[str],
    ) -> str:
        """Детерминированный ключ для блока enrichment."""
        normalized_files = ",".join(sorted(item.strip() for item in changed_files if item.strip()))
        raw = f"{agent_id}|{path_prefix}|{instruction}|{normalized_files}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def get(self, key: str) -> list[str] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, lines = entry
        if time.monotonic() > expires_at:
            self._entries.pop(key, None)
            return None
        return list(lines)

    def put(self, key: str, lines: list[str]) -> None:
        if self.ttl_seconds <= 0 or not lines:
            return
        expires_at = time.monotonic() + float(self.ttl_seconds)
        self._entries[key] = (expires_at, list(lines))

    def clear(self) -> None:
        self._entries.clear()
