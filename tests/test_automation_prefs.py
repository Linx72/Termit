from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.services.automation_control_service import AutomationControlService
from app.services.env_file_service import EnvFileService


class EnvFileServiceTests(unittest.TestCase):
    def test_set_and_read_bool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("TERMIT_STAGE1_SCHEDULE_ENABLED=false\n", encoding="utf-8")
            service = EnvFileService(str(path))
            service.set_key("TERMIT_DAILY_IMPROVEMENT_ENABLED", "true")
            self.assertTrue(service.read_bool("TERMIT_DAILY_IMPROVEMENT_ENABLED"))
            self.assertFalse(service.read_bool("TERMIT_STAGE1_SCHEDULE_ENABLED"))


class AutomationControlServiceTests(unittest.TestCase):
    def test_apply_writes_env_and_stops_stage1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("TERMIT_STAGE1_SCHEDULE_ENABLED=true\n", encoding="utf-8")
            stage1 = MagicMock()
            service = AutomationControlService(
                env_service=EnvFileService(str(path)),
                stage1_scheduler=stage1,
                project_root=tmp,
            )
            result = service.apply({"stage1_schedule": False})
            self.assertIn("stage1_schedule", result.get("applied", []))
            stage1.set_enabled.assert_called_once_with(False)
            self.assertEqual(
                EnvFileService(str(path)).read_value("TERMIT_STAGE1_SCHEDULE_ENABLED"),
                "false",
            )


class AutomationPrefsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._env_path = Path(self._tmpdir.name) / ".env"
        self._env_path.write_text(
            "TERMIT_STAGE1_SCHEDULE_ENABLED=false\n"
            "TERMIT_DAILY_IMPROVEMENT_ENABLED=false\n",
            encoding="utf-8",
        )
        self._previous = os.environ.get("TERMIT_ENV_FILE")
        os.environ["TERMIT_ENV_FILE"] = str(self._env_path)
        from app.state import _build_automation_control_service

        _build_automation_control_service.cache_clear()

    def tearDown(self) -> None:
        from app.state import _build_automation_control_service

        _build_automation_control_service.cache_clear()
        if self._previous is None:
            os.environ.pop("TERMIT_ENV_FILE", None)
        else:
            os.environ["TERMIT_ENV_FILE"] = self._previous
        self._tmpdir.cleanup()

    def test_get_automation_endpoint(self) -> None:
        client = TestClient(app)
        response = client.get("/api/ops/automation")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("toggles", payload)
        ids = {item["toggle_id"] for item in payload["toggles"]}
        self.assertIn("stage1_schedule", ids)

    def test_patch_automation_updates_env(self) -> None:
        client = TestClient(app)
        response = client.patch(
            "/api/ops/automation",
            json={"toggles": {"daily_improvement": True}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("daily_improvement", response.json().get("applied", []))
        text = self._env_path.read_text(encoding="utf-8")
        self.assertIn("TERMIT_DAILY_IMPROVEMENT_ENABLED=true", text)
