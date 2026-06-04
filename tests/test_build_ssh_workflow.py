import unittest
from unittest.mock import MagicMock, patch

from app.services.build_workflow_service import BuildWorkflowService
from app.services.ssh_workspace_service import SshWorkspaceConfig, SshWorkspaceService


class BuildWorkflowServiceTests(unittest.TestCase):
    def test_detects_website_task(self) -> None:
        self.assertTrue(BuildWorkflowService.is_build_task("Создай сайт на React"))

    def test_enrich_includes_phases(self) -> None:
        text = BuildWorkflowService.enrich_agent_input(
            "Landing page",
            execution_mode="hybrid",
            workspace="/tmp/app",
        )
        self.assertIn("Фаза 1", text)
        self.assertIn("Landing page", text)


class SshWorkspaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.local = MagicMock()
        self.local._classify_command.return_value = ("safe", "ok")
        self.service = SshWorkspaceService(self.local)

    @patch("app.services.ssh_workspace_service.subprocess.run")
    def test_connection_ok(self, run_mock: MagicMock) -> None:
        run_mock.return_value = MagicMock(returncode=0, stdout="OK\n", stderr="")
        cfg = SshWorkspaceConfig(
            host="example.com",
            user="deploy",
            remote_path="/var/www",
        )
        ok, detail = self.service.test_connection(cfg)
        self.assertTrue(ok)
        self.assertIn("OK", detail)

    def test_from_run_payload_requires_fields(self) -> None:
        self.assertIsNone(
            SshWorkspaceService.from_run_payload(ssh_host="h", ssh_user="", ssh_remote_path="/x")
        )


if __name__ == "__main__":
    unittest.main()
