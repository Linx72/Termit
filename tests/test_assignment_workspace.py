from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import AssignmentCreateRequest, TaskType
from app.services.assignment_workspace_service import AssignmentWorkspaceService
from app.services.task_service import TaskService
from app.services.task_store import InMemoryTaskStore
from app.services.tooling_service import ToolingService


class AssignmentWorkspaceTests(unittest.TestCase):
    def test_create_assignment_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = AssignmentWorkspaceService(tmp)
            created = service.create(
                AssignmentCreateRequest(
                    title="Demo Online Project",
                    brief="Research competitors and write summary.",
                    success_criteria=["report.md"],
                    target_urls=["https://example.com"],
                )
            )
            self.assertTrue(Path(created.brief_path).is_file())
            self.assertTrue(Path(created.deliverables_path).is_dir())
            listed = service.list_assignments()
            self.assertEqual(len(listed), 1)


class OnlineProjectTaskTests(unittest.TestCase):
    def test_online_project_plan_includes_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assignments = AssignmentWorkspaceService(f"{tmp}/assignments")
            tooling = ToolingService(root_path=tmp)
            store = InMemoryTaskStore()
            service = TaskService(
                tooling,
                store,
                assignment_workspace=assignments,
            )
            from app.domain.schemas import TaskCreateRequest, TaskMode

            result = service.create_task(
                TaskCreateRequest(
                    input="Build competitor report for Termit",
                    task_type=TaskType.online_project,
                    mode=TaskMode.auto,
                )
            )
            task = service.get_task(result.task_id)
            event_types = [event.event_type for event in task.events]
            self.assertIn("plan_ready", event_types)
            self.assertEqual(task.state.value, "completed")
