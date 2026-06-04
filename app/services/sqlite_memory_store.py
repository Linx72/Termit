import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Lock

from app.domain.schemas import ChatMessage


class SQLiteMemoryStore:
    def __init__(self, db_path: str, max_messages_per_session: int = 40) -> None:
        self.db_path = str(Path(db_path).resolve())
        self.max_messages_per_session = max_messages_per_session
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_session_messages_session_id "
                "ON session_messages(session_id, id)"
            )
            conn.commit()

    def append(self, session_id: str, message: ChatMessage) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO session_messages(session_id, role, content) VALUES (?, ?, ?)",
                (session_id, message.role, message.content),
            )
            conn.execute(
                """
                DELETE FROM session_messages
                WHERE session_id = ?
                  AND id NOT IN (
                    SELECT id FROM session_messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (session_id, session_id, self.max_messages_per_session),
            )
            conn.commit()

    def get(self, session_id: str) -> list[ChatMessage]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM session_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [ChatMessage(role=row["role"], content=row["content"]) for row in rows]

    def clear(self, session_id: str) -> bool:
        with self._lock, closing(self._connect()) as conn:
            cursor = conn.execute(
                "DELETE FROM session_messages WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
