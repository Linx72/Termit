from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class WebDashboardMcpPanelTests(unittest.TestCase):
    def test_index_html_contains_mcp_dashboard_cards(self) -> None:
        html = Path("app/web/templates/index.html").read_text(encoding="utf-8")
        self.assertIn("dashMcpInjectCard", html)
        self.assertIn("dashMcpToolsCard", html)
        self.assertIn("dashMcpAdoptionCard", html)
        self.assertIn("mcp_inject_rate", html)

    def test_agent_runs_metrics_exposes_mcp_fields(self) -> None:
        client = TestClient(app)
        response = client.get("/api/ops/agent-runs/metrics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in (
            "mcp_context_inject_total",
            "mcp_prompt_inject_total",
            "mcp_tool_calls_total",
            "mcp_inject_rate",
            "mcp_active_runs",
        ):
            self.assertIn(key, payload)


if __name__ == "__main__":
    unittest.main()
