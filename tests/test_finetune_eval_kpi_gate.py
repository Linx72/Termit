import importlib.util
import unittest
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "finetune_eval_kpi_gate.py"
    spec = importlib.util.spec_from_file_location("finetune_eval_kpi_gate", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FinetuneEvalKpiGateTests(unittest.TestCase):
    def test_kpi_passes_at_five_percent(self) -> None:
        mod = _load_module()
        summary = mod.evaluate_improvement_kpi(
            baseline_pass_rate=0.70,
            current_pass_rate=0.75,
            min_improvement=0.05,
        )
        self.assertTrue(summary["kpi_passed"])
        self.assertAlmostEqual(summary["delta"], 0.05)

    def test_kpi_fails_below_target(self) -> None:
        mod = _load_module()
        summary = mod.evaluate_improvement_kpi(
            baseline_pass_rate=0.93,
            current_pass_rate=0.94,
            min_improvement=0.05,
        )
        self.assertFalse(summary["kpi_passed"])

    def test_kpi_missing_baseline(self) -> None:
        mod = _load_module()
        summary = mod.evaluate_improvement_kpi(
            baseline_pass_rate=None,
            current_pass_rate=0.80,
            min_improvement=0.05,
        )
        self.assertFalse(summary["kpi_passed"])
        self.assertIn("Baseline", summary["reason"])


if __name__ == "__main__":
    unittest.main()
