from __future__ import annotations

import unittest

from app.services.eval_ci_gate import evaluate_ci_gate


class EvalCiGateTests(unittest.TestCase):
    def test_passes_at_threshold(self) -> None:
        ok, message = evaluate_ci_gate(pass_rate=0.95, min_rate=0.95, total=20)
        self.assertTrue(ok)
        self.assertIn("passed", message)

    def test_fails_below_threshold(self) -> None:
        ok, message = evaluate_ci_gate(pass_rate=0.5, min_rate=0.95, total=20)
        self.assertFalse(ok)
        self.assertIn("below minimum", message)

    def test_fails_on_empty_suite(self) -> None:
        ok, _ = evaluate_ci_gate(pass_rate=1.0, min_rate=0.95, total=0)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
