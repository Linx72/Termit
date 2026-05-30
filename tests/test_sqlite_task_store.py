import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import TaskCreateRequest, TaskMode, TaskState, TaskType
from app.services.sqlite_task_store import SQLiteTaskStore
from app.services.task_service import TaskService
from app.services.tooling_service import ToolingService


class SQLiteTaskStoreTests(unittest.TestCase):
    def test_task_persists_across_service_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "tasks.db")
            store = SQLiteTaskStore(db_path)
            tooling = ToolingService(root_path=".")

            first = TaskService(tooling, store, max_attempts=2)
            created = first.create_task(
                TaskCreateRequest(
                    input="Prepare execution report [retry-demo]",
                    task_type=TaskType.coding,
                )
            )

            second = TaskService(tooling, store, max_attempts=2)
            task = second.get_task(created.task_id)
            self.assertEqual(task.state, TaskState.completed)
            listed = second.list_tasks(limit=10)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].task_id, created.task_id)

    def test_guided_task_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "tasks.db")
            store = SQLiteTaskStore(db_path)
            service = TaskService(ToolingService(root_path="."), store)
            created = service.create_task(
                TaskCreateRequest(
                    input="Guide me step by step",
                    task_type=TaskType.review,
                    mode=TaskMode.guided,
                )
            )
            task = service.get_task(created.task_id)
            self.assertEqual(task.state, TaskState.running)


if __name__ == "__main__":
    unittest.main()
