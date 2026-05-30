import unittest

from app.domain.schemas import TaskCreateRequest, TaskMode, TaskType
from app.services.task_service import TaskService
from app.services.task_store import InMemoryTaskStore
from app.services.tooling_service import ToolingService


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TaskService(
            ToolingService(root_path="."),
            InMemoryTaskStore(),
            max_attempts=2,
        )

    def test_transient_error_retries_and_completes(self) -> None:
        created = self.service.create_task(
            TaskCreateRequest(
                input="Prepare execution report [retry-demo]",
                task_type=TaskType.coding,
            )
        )
        task = self.service.get_task(created.task_id)
        self.assertEqual(task.state.value, "completed")
        self.assertEqual(task.attempts, 2)
        self.assertIn("retry_scheduled", [event.event_type for event in task.events])

    def test_verification_failure_sets_failure_class(self) -> None:
        created = self.service.create_task(
            TaskCreateRequest(
                input="Run checks and verify output [fail-verify]",
                task_type=TaskType.general,
            )
        )
        task = self.service.get_task(created.task_id)
        self.assertEqual(task.state.value, "failed")
        self.assertEqual(task.failure_class, "verification_error")
        self.assertIsNotNone(task.error)

    def test_guided_mode_stays_running(self) -> None:
        created = self.service.create_task(
            TaskCreateRequest(
                input="Guide me step by step through changes",
                task_type=TaskType.review,
                mode=TaskMode.guided,
            )
        )
        task = self.service.get_task(created.task_id)
        self.assertEqual(task.state.value, "running")
        self.assertIn("guided mode", (task.report or "").lower())


if __name__ == "__main__":
    unittest.main()
