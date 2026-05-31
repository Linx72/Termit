from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock


class EmbeddingCache:
    def __init__(self, db_path: str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_embeddings (
                chunk_id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                embedding_json TEXT NOT NULL
            )
            """
        )
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.commit()
            finally:
                conn.close()

    def get(self, chunk_id: str) -> list[float] | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT embedding_json FROM chunk_embeddings WHERE chunk_id = ?",
                    (chunk_id,),
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        payload = json.loads(row[0])
        if not isinstance(payload, list):
            return None
        return [float(item) for item in payload]

    def put(self, chunk_id: str, *, path: str, line_start: int, content_hash: str, embedding: list[float]) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chunk_embeddings
                    (chunk_id, path, line_start, content_hash, embedding_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk_id, path, line_start, content_hash, json.dumps(embedding)),
                )
                conn.commit()
            finally:
                conn.close()

    def count(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()
            finally:
                conn.close()
        return int(row[0]) if row else 0
