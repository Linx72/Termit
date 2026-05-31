import unittest

from app.services.finetune_regression_gate import evaluate_training_regression


class FinetuneRegressionGateTests(unittest.TestCase):
    def test_promote_when_improved(self) -> None:
        decision = evaluate_training_regression(
            baseline_pass_rate=0.70,
            post_pass_rate=0.80,
        )
        self.assertTrue(decision.promote)
        self.assertFalse(decision.use_shadow)

    def test_shadow_on_regression(self) -> None:
        decision = evaluate_training_regression(
            baseline_pass_rate=0.80,
            post_pass_rate=0.70,
            max_regression=0.02,
        )
        self.assertFalse(decision.promote)
        self.assertTrue(decision.use_shadow)

    def test_promote_when_no_baseline(self) -> None:
        decision = evaluate_training_regression(
            baseline_pass_rate=None,
            post_pass_rate=0.60,
        )
        self.assertTrue(decision.promote)


if __name__ == "__main__":
    unittest.main()
