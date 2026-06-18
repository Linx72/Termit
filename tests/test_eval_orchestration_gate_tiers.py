"""Tests for orchestration gate tier presets."""

from __future__ import annotations

import os
import unittest

from app.services.eval_orchestration_gate_tiers import (
    CI_GATE,
    LOCAL_GATE,
    apply_orchestration_gate_tier,
)


class EvalOrchestrationGateTierTests(unittest.TestCase):
    def test_apply_ci_tier(self) -> None:
        with self._clean_env():
            tier = apply_orchestration_gate_tier("ci", overwrite=True)
            assert tier is not None
            self.assertEqual(tier.name, CI_GATE.name)
            self.assertEqual(os.environ["TERMIT_ORCH_MIN_TOOL_LOOP_STEPS"], "0")
            self.assertEqual(os.environ["TERMIT_ORCH_REQUIRE_TOOL_LOOP"], "false")

    def test_apply_local_tier_requires_tool_loop(self) -> None:
        with self._clean_env():
            tier = apply_orchestration_gate_tier("local", overwrite=True)
            assert tier is not None
            self.assertEqual(tier.name, LOCAL_GATE.name)
            self.assertEqual(os.environ["TERMIT_ORCH_REQUIRE_TOOL_LOOP"], "true")
            self.assertEqual(os.environ["TERMIT_ORCH_MIN_TOOL_LOOP_STEPS"], "1")

    def test_apply_strict_live_disables_fallback(self) -> None:
        with self._clean_env():
            tier = apply_orchestration_gate_tier("strict_live", overwrite=True)
            assert tier is not None
            self.assertEqual(os.environ["TERMIT_ORCH_TOOL_LOOP_FALLBACK"], "false")
            self.assertEqual(os.environ["TERMIT_ORCH_MAX_TOOL_LOOP_FALLBACK_DELTA"], "0.0")
            self.assertEqual(os.environ["TERMIT_ORCH_MIN_PASS_RATE"], "1.0")

    def _clean_env(self):
        keys = [
            "TERMIT_ORCH_MIN_PASS_RATE",
            "TERMIT_ORCH_MIN_RETRY_SUCCESS_RATE",
            "TERMIT_ORCH_MIN_TOTAL",
            "TERMIT_ORCH_MIN_TOOL_LOOP_STEPS",
            "TERMIT_ORCH_REQUIRE_TOOL_LOOP",
            "TERMIT_ORCH_TOOL_LOOP_FALLBACK",
            "TERMIT_ORCH_MAX_TOOL_LOOP_FALLBACK_DELTA",
        ]
        return _EnvCleaner(keys)


class _EnvCleaner:
    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self._backup: dict[str, str | None] = {}

    def __enter__(self) -> _EnvCleaner:
        for key in self._keys:
            self._backup[key] = os.environ.get(key)
            os.environ.pop(key, None)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for key, value in self._backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
