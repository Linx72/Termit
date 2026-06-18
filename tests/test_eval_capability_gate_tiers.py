"""Tests for capability gate tier presets."""

from __future__ import annotations

import os
import unittest

from app.services.eval_capability_gate_tiers import (
    CI_GATE,
    RELEASE_GATE,
    apply_capability_gate_tier,
)


class EvalCapabilityGateTierTests(unittest.TestCase):
    def test_apply_ci_tier_sets_relaxed_thresholds(self) -> None:
        with self._clean_cap_env():
            tier = apply_capability_gate_tier("ci", overwrite=True)
            assert tier is not None
            self.assertEqual(tier.name, CI_GATE.name)
            self.assertEqual(os.environ["TERMIT_CAP_MIN_REPORTS"], "1")
            self.assertEqual(os.environ["TERMIT_CAP_ALLOWED_TRENDS"], "flat,improving,regressing,no_data")

    def test_apply_release_tier_sets_production_thresholds(self) -> None:
        with self._clean_cap_env():
            tier = apply_capability_gate_tier("release", overwrite=True)
            assert tier is not None
            self.assertEqual(tier.name, RELEASE_GATE.name)
            self.assertEqual(os.environ["TERMIT_CAP_MIN_REPORTS"], "2")
            self.assertEqual(os.environ["TERMIT_CAP_MIN_WIN_RATE"], "0.4")

    def test_unknown_tier_returns_none(self) -> None:
        self.assertIsNone(apply_capability_gate_tier("unknown"))

    def _clean_cap_env(self):
        keys = [
            "TERMIT_CAP_MIN_REPORTS",
            "TERMIT_CAP_MIN_MEAN_PASS_GAP",
            "TERMIT_CAP_MIN_MEAN_QUALITY_GAP",
            "TERMIT_CAP_MIN_WIN_RATE",
            "TERMIT_CAP_ALLOWED_TRENDS",
            "TERMIT_CAP_REG_MAX_PASS_GAP_DROP",
            "TERMIT_CAP_REG_MAX_QUALITY_GAP_DROP",
            "TERMIT_CAP_REG_MAX_WIN_RATE_DROP",
        ]
        return _CapEnvCleaner(keys)


class _CapEnvCleaner:
    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self._backup: dict[str, str | None] = {}

    def __enter__(self) -> _CapEnvCleaner:
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
