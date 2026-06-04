import unittest

from app.services.agent_loop_service import build_loop_system_appendix


class AgentLoopAppendixTests(unittest.TestCase):
    def test_appendix_lists_only_enabled_tools(self) -> None:
        appendix = build_loop_system_appendix(["web_automation"])
        self.assertIn("web_automation", appendix)
        self.assertNotIn("list_files", appendix)
        self.assertNotIn("read_file", appendix)

    def test_appendix_includes_file_tool_examples_when_enabled(self) -> None:
        appendix = build_loop_system_appendix(["list_files", "read_file"])
        self.assertIn("list_files", appendix)
        self.assertIn("read_file", appendix)
        self.assertNotIn("web_automation", appendix)

    def test_appendix_final_only_when_no_tools(self) -> None:
        appendix = build_loop_system_appendix([])
        self.assertIn('"action":"final"', appendix)
        self.assertNotIn("list_files", appendix)


if __name__ == "__main__":
    unittest.main()
