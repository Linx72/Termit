from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.eval_orchestration_spike import (
    _load_prompts_from_file,
    _load_scenarios_from_file,
    _write_json_atomic,
)


class EvalOrchestrationSpikeTests(unittest.TestCase):
    def test_load_prompts_from_mixed_json_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompts.json"
            path.write_text(
                json.dumps(
                    [
                        {"prompt": "Prompt A"},
                        "Prompt B",
                        {"id": "x"},
                        "   ",
                    ]
                ),
                encoding="utf-8",
            )
            prompts = _load_prompts_from_file(path)
            self.assertEqual(prompts, ["Prompt A", "Prompt B"])

    def test_load_scenarios_marks_expect_tool_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompts.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "ORCH11", "prompt": "Inspect tools", "expect_tool_loop": True},
                        {"id": "ORCH1", "prompt": "Plain"},
                    ]
                ),
                encoding="utf-8",
            )
            scenarios = _load_scenarios_from_file(path)
            self.assertEqual(len(scenarios), 2)
            self.assertTrue(scenarios[0]["expect_tool_loop"])
            self.assertFalse(scenarios[1]["expect_tool_loop"])

    def test_write_json_atomic_produces_valid_single_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            payload = {"total": 2, "pass_rate": 0.5, "metrics_after": {"coder_retry_success_rate": 0.4}}
            _write_json_atomic(target, payload)
            loaded = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(loaded["total"], 2)
            self.assertEqual(loaded["metrics_after"]["coder_retry_success_rate"], 0.4)


if __name__ == "__main__":
    unittest.main()
