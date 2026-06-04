from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from threading import Lock


class ResponseCacheStore:
    def __init__(self, backend: str = "memory", sqlite_path: str = "./termit_cache.db") -> None:
        self.backend = backend
        self.sqlite_path = str(Path(sqlite_path).resolve())
        self._lock = Lock()
        self._memory: dict[str, tuple[float, str]] = {}
        if self.backend == "sqlite":
            self._init_db()

    def get(self, key: str) -> str | None:
        now = time.time()
        if self.backend == "sqlite":
            with self._lock, closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT value, expires_at FROM response_cache WHERE cache_key = ?",
                    (key,),
                ).fetchone()
                if not row:
                    return None
                if row["expires_at"] < now:
                    conn.execute("DELETE FROM response_cache WHERE cache_key = ?", (key,))
                    conn.commit()
                    return None
                return str(row["value"])

        with self._lock:
            item = self._memory.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < now:
                self._memory.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        expires_at = time.time() + ttl_seconds
        if self.backend == "sqlite":
            with self._lock, closing(self._connect()) as conn:
                conn.execute(
                    """
                    INSERT INTO response_cache(cache_key, value, expires_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        value = excluded.value,
                        expires_at = excluded.expires_at
                    """,
                    (key, value, expires_at),
                )
                conn.commit()
            return

        with self._lock:
            self._memory[key] = (expires_at, value)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS response_cache (
                    cache_key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.commit()
