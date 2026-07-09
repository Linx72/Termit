import unittest

from app.services.tool_loop_metrics import aggregate_tool_loop_events, classify_tool_loop_event


class ToolLoopMetricsTests(unittest.TestCase):
    def test_classify_legacy_step_events(self) -> None:
        self.assertEqual(
            classify_tool_loop_event("tool_loop_step", "Step 2: tool (apply_patch)"),
            "tool_loop_tool",
        )
        self.assertEqual(
            classify_tool_loop_event("tool_loop_step", "Step 3: parse_error"),
            "tool_loop_parse_error",
        )
        self.assertEqual(
            classify_tool_loop_event("patch_verify", "Verify after patch: exit_code=0"),
            "tool_loop_verify_pass",
        )
        self.assertEqual(
            classify_tool_loop_event("patch_verify_failed", "Verify after patch: exit_code=1"),
            "tool_loop_verify_failed",
        )

    def test_aggregate_rates(self) -> None:
        rows = [
            ("run-1", "tool_loop_tool", "Step 1: tool (read_file)"),
            ("run-1", "tool_loop_tool_error", "Step 2: tool (apply_patch)"),
            ("run-1", "tool_loop_final", "Step 3: final"),
            ("run-1", "tool_loop_verify_pass", "Step 3: verify_pass"),
            ("run-2", "tool_loop_parse_error", "Step 1: parse_error"),
            ("run-2", "tool_loop_verify_failed", "Step 2: verify_failed"),
            ("run-2", "verify_retry_scheduled", "Step 2: verify_retry"),
        ]
        metrics = aggregate_tool_loop_events(rows, completed_run_ids={"run-1"})
        self.assertEqual(metrics["tool_loop_runs"], 2)
        self.assertEqual(metrics["tool_loop_tool_steps"], 1)
        self.assertEqual(metrics["tool_loop_tool_errors"], 1)
        self.assertEqual(metrics["tool_loop_verify_passes"], 1)
        self.assertEqual(metrics["tool_loop_verify_failures"], 1)
        self.assertEqual(metrics["tool_loop_verify_retries"], 1)
        self.assertEqual(metrics["tool_loop_verify_pass_rate"], 0.5)
        self.assertEqual(metrics["tool_loop_tool_success_rate"], 0.5)
        self.assertEqual(metrics["tool_loop_completion_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
