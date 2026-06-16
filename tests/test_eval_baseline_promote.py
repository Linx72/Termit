import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_promote_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "eval_baseline_promote.py"
    spec = importlib.util.spec_from_file_location("eval_baseline_promote", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class EvalBaselinePromoteTests(unittest.TestCase):
    @staticmethod
    def _write_report(path: Path, pass_rate: float) -> None:
        path.write_text(
            json.dumps({"pass_rate": pass_rate, "total": 10, "results": []}, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_promote_on_green_gate(self) -> None:
        mod = _load_promote_module()
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            current = Path(tmp) / "current.json"
            self._write_report(baseline, 0.70)
            self._write_report(current, 0.80)
            ok, summary = mod.promote_baseline(
                baseline_path=baseline,
                current_path=current,
                max_pass_rate_drop=0.05,
                min_improvement=0.0,
                dry_run=False,
            )
            self.assertTrue(ok)
            self.assertTrue(summary["promoted"])
            updated = json.loads(baseline.read_text(encoding="utf-8"))
            self.assertEqual(updated["pass_rate"], 0.80)

    def test_skip_promote_on_regression(self) -> None:
        mod = _load_promote_module()
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            current = Path(tmp) / "current.json"
            self._write_report(baseline, 0.90)
            self._write_report(current, 0.70)
            ok, summary = mod.promote_baseline(
                baseline_path=baseline,
                current_path=current,
                max_pass_rate_drop=0.05,
                min_improvement=0.0,
                dry_run=False,
            )
            self.assertFalse(ok)
            self.assertFalse(summary["promoted"])
            self.assertEqual(json.loads(baseline.read_text(encoding="utf-8"))["pass_rate"], 0.90)


if __name__ == "__main__":
    unittest.main()
