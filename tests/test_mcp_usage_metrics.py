from __future__ import annotations

import unittest

from app.services.mcp_usage_metrics import aggregate_mcp_usage_events, empty_mcp_usage_metrics


class McpUsageMetricsTests(unittest.TestCase):
    def test_empty_metrics(self) -> None:
        payload = empty_mcp_usage_metrics()
        self.assertEqual(payload["mcp_tool_calls_total"], 0)
        self.assertEqual(payload["mcp_inject_rate"], 0.0)

    def test_aggregate_inject_and_tool_events(self) -> None:
        rows = [
            ("run1", "mcp_context_injected", '{"lines": 5}'),
            ("run1", "tool_loop_tool", "Step 2: tool (mcp_invoke)"),
            ("run2", "mcp_prompt_injected", '{"lines": 3}'),
            ("run3", "tool_loop_tool", "Step 1: tool (mcp_read_resource)"),
            ("run4", "tool_loop_step", "Step 1: final"),
        ]
        payload = aggregate_mcp_usage_events(rows)
        self.assertEqual(payload["mcp_context_inject_total"], 1)
        self.assertEqual(payload["mcp_prompt_inject_total"], 1)
        self.assertEqual(payload["mcp_invoke_total"], 1)
        self.assertEqual(payload["mcp_read_resource_total"], 1)
        self.assertEqual(payload["mcp_tool_calls_total"], 2)
        self.assertEqual(payload["mcp_inject_runs"], 2)
        self.assertEqual(payload["mcp_active_runs"], 3)
        self.assertAlmostEqual(float(payload["mcp_inject_rate"]), 2 / 3, places=4)


if __name__ == "__main__":
    unittest.main()
