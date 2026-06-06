import unittest
import time
from tempfile import TemporaryDirectory

from app.domain.schemas import AgentProfileCreateRequest, TaskCreateRequest, TaskType
from app.services.agent_registry_store import AgentRegistryStore
from app.state import _pick_existing_agent_id, _pick_template_for_task, _resolve_task_agent_id
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.task_agent_assignment import resolve_project_template_ids
from app.services.task_service import TaskService
from app.services.task_store import InMemoryTaskStore
from app.services.tooling_service import ToolingService


class TaskAgentAssignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.registry = AgentRegistryStore(file_path=f"{self.tmpdir.name}/agents.assignment.test.json")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_pick_template_by_task_type_and_intent(self) -> None:
        self.assertEqual(_pick_template_for_task(TaskType.online_project, "Build assignment"), "online-project-manager")
        self.assertEqual(_pick_template_for_task(TaskType.online_research, "Do deep market research"), "research-deep")
        self.assertEqual(_pick_template_for_task(TaskType.creative_media, "Render storyboard video"), "studio-director")
        self.assertEqual(_pick_template_for_task(TaskType.coding, "Add tests for API"), "write-tests")
        self.assertEqual(
            resolve_project_template_ids(TaskType.coding, "Need ci fixes and tests"),
            ["termit-platform-dev", "write-tests", "fix-ci"],
        )

    def test_pick_existing_agent_prefers_matching_task_type(self) -> None:
        coding = self.registry.create_agent(
            AgentProfileCreateRequest(
                name="Coding Worker",
                description="",
                system_prompt="coding",
                task_type=TaskType.coding,
            )
        )
        research = self.registry.create_agent(
            AgentProfileCreateRequest(
                name="Research Worker",
                description="",
                system_prompt="research",
                task_type=TaskType.online_research,
                allow_online=True,
            )
        )
        selected = _pick_existing_agent_id([coding, research], TaskType.online_research, "Need web research")
        self.assertEqual(selected, research.agent_id)

    def test_preferred_agent_id_has_priority(self) -> None:
        class StubService:
            def list_agents(self):
                return []

            def create_agent(self, request):
                raise AssertionError("create_agent must not be called for preferred id")

        selected = _resolve_task_agent_id(
            input_text="Investigate issue",
            requested_task_type=TaskType.general,
            preferred_agent_id="agent_preferred",
            project_id=None,
            service=StubService(),
        )
        self.assertEqual(selected, "agent_preferred")

    def test_project_task_auto_attaches_multiple_agents(self) -> None:
        templates = AgentTemplatesStore(file_path="/Users/amoros/Projects/Termit/data/agent_templates.json")
        service = TaskService(
            ToolingService(root_path="."),
            InMemoryTaskStore(),
            agent_runner=lambda input_text, task_type, session_id, project_id: "ok",
            use_agent_for_auto=True,
            agent_registry=self.registry,
            agent_templates=templates,
        )
        created = service.create_task(
            TaskCreateRequest(
                input="Need CI fix and tests for project pipeline",
                task_type=TaskType.coding,
                project_id="demo-project",
            )
        )
        deadline = time.time() + 2.0
        task = service.get_task(created.task_id)
        while task.state.value in {"queued", "running"} and time.time() < deadline:
            time.sleep(0.05)
            task = service.get_task(created.task_id)
        event_types = [event.event_type for event in task.events]
        self.assertIn("project_agents_attached", event_types)
        agent_names = {agent.name for agent in self.registry.list_agents()}
        self.assertIn("Termit Platform Dev", agent_names)
        self.assertIn("Write Tests", agent_names)
        self.assertIn("Fix CI", agent_names)


if __name__ == "__main__":
    unittest.main()
