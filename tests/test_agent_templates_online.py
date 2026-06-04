from __future__ import annotations

import unittest

from app.services.agent_templates_store import AgentTemplatesStore


class AgentTemplatesOnlineTests(unittest.TestCase):
    def test_web_templates_allow_online(self) -> None:
        store = AgentTemplatesStore(file_path="data/agent_templates.json")
        for template_id in (
            "web-app-vite",
            "research-fast",
            "online-project-manager",
            "termit-desktop-autopilot",
        ):
            template = store.get_template(template_id)
            self.assertIsNotNone(template, template_id)
            assert template is not None
            self.assertTrue(template.allow_online, template_id)
            request = store.to_create_request(template_id)
            self.assertTrue(request.allow_online)

    def test_desktop_guided_template_exists(self) -> None:
        store = AgentTemplatesStore(file_path="data/agent_templates.json")
        template = store.get_template("termit-desktop-guided")
        self.assertIsNotNone(template)
        assert template is not None
        self.assertFalse(template.allow_online)
        self.assertIn("agent-guided", template.skill_ids or [])
