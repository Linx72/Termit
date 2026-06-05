import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Lock
from typing import Optional

from app.domain.schemas import TaskEvent, TaskStatusResponse


class SQLiteTaskStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = str(Path(db_path).resolve())
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
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    input TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    session_id TEXT,
                    project_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    report TEXT,
                    error TEXT,
                    failure_class TEXT,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL
                )
                """
            )
            columns = {
                str(item["name"]): str(item["type"])
                for item in conn.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "project_id" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_events_task_id ON task_events(task_id, id)"
            )
            conn.commit()

    def put_task(self, task: TaskStatusResponse) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, state, input, task_type, mode, session_id, project_id,
                    created_at, updated_at, report, error, failure_class,
                    attempts, max_attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    state=excluded.state,
                    input=excluded.input,
                    task_type=excluded.task_type,
                    mode=excluded.mode,
                    session_id=excluded.session_id,
                    project_id=excluded.project_id,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    report=excluded.report,
                    error=excluded.error,
                    failure_class=excluded.failure_class,
                    attempts=excluded.attempts,
                    max_attempts=excluded.max_attempts
                """,
                (
                    task.task_id,
                    task.state.value,
                    task.input,
                    task.task_type.value,
                    task.mode.value,
                    task.session_id,
                    task.project_id,
                    task.created_at,
                    task.updated_at,
                    task.report,
                    task.error,
                    task.failure_class,
                    task.attempts,
                    task.max_attempts,
                ),
            )
            conn.execute("DELETE FROM task_events WHERE task_id = ?", (task.task_id,))
            for event in task.events:
                conn.execute(
                    """
                    INSERT INTO task_events(task_id, event_type, state, message, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        event.event_type,
                        event.state.value,
                        event.message,
                        event.timestamp,
                    ),
                )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[TaskStatusResponse]:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            events = conn.execute(
                """
                SELECT event_type, state, message, timestamp
                FROM task_events
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (task_id,),
            ).fetchall()
        return self._row_to_task(row, events)

    def list_tasks(self, limit: int = 50) -> list[TaskStatusResponse]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            tasks: list[TaskStatusResponse] = []
            for row in rows:
                events = conn.execute(
                    """
                    SELECT event_type, state, message, timestamp
                    FROM task_events
                    WHERE task_id = ?
                    ORDER BY id ASC
                    """,
                    (row["task_id"],),
                ).fetchall()
                task = self._row_to_task(row, events)
                if task is not None:
                    tasks.append(task)
        return tasks

    def _row_to_task(self, row: sqlite3.Row, events: list[sqlite3.Row]) -> TaskStatusResponse:
        from app.domain.schemas import TaskMode, TaskState, TaskType

        return TaskStatusResponse(
            task_id=row["task_id"],
            state=TaskState(row["state"]),
            input=row["input"],
            task_type=TaskType(row["task_type"]),
            mode=TaskMode(row["mode"]),
            session_id=row["session_id"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            report=row["report"],
            error=row["error"],
            failure_class=row["failure_class"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            events=[
                TaskEvent(
                    event_type=event["event_type"],
                    state=TaskState(event["state"]),
                    message=event["message"],
                    timestamp=event["timestamp"],
                )
                for event in events
            ],
        )
