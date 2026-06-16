from __future__ import annotations

import sys
import unittest
from pathlib import Path

from app.services.mcp_registry_service import McpRegistryService
from app.services.mcp_stdio_client import McpStdioSession
from app.services.playwright_browser_service import PlaywrightBrowserService


class McpBrowserServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script_path = Path(__file__).resolve().parents[1] / "scripts" / "mcp_termit_browser.py"
        cls.registry_path = Path(__file__).resolve().parents[1] / "data" / "mcp_servers.json"

    def test_bundled_preset_exists(self) -> None:
        registry = McpRegistryService(str(self.registry_path))
        servers = {item.server_id: item for item in registry.list_servers()}
        self.assertIn("termit-browser", servers)
        preset = servers["termit-browser"]
        self.assertFalse(preset.enabled)
        self.assertIn("mcp_termit_browser.py", " ".join(preset.args))

    def test_browser_mcp_lists_tools(self) -> None:
        session = McpStdioSession(command=sys.executable, args=[str(self.script_path)])
        try:
            tools = session.list_tools()
            names = [item.name for item in tools]
            self.assertEqual(
                names,
                ["browser_navigate", "browser_snapshot", "browser_click"],
            )
        finally:
            session.close()

    def test_browser_navigate_when_playwright_available(self) -> None:
        probe = PlaywrightBrowserService()
        if not probe.available():
            self.skipTest("playwright package not installed")
        try:
            probe.navigate("https://example.com", timeout_seconds=20)
        except Exception as exc:  # noqa: BLE001 — skip when chromium missing
            probe.close()
            self.skipTest(f"playwright runtime unavailable: {exc}")
        probe.close()

        session = McpStdioSession(command=sys.executable, args=[str(self.script_path)])
        try:
            result = session.call_tool(
                "browser_navigate",
                {"url": "https://example.com", "timeout_seconds": 30},
            )
            self.assertIn("content", result)
            text = result["content"][0]["text"]
            self.assertIn("example.com", text)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
