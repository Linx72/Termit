from __future__ import annotations

import unittest

from app.services.finetune_dpo_export import build_dpo_pairs, validate_dpo_rows


class FinetuneDpoExportTests(unittest.TestCase):
    def test_build_dpo_pairs_matches_instruction(self) -> None:
        negatives = [
            {
                "instruction": "Fix middleware auth",
                "rejected": "Removed all auth checks entirely.",
                "category": "tool_loop_negative",
            }
        ]
        positives = [
            {
                "instruction": "Fix middleware auth",
                "output": "Added RBAC check before handler execution.",
                "quality_score": "1.0",
            }
        ]
        pairs = build_dpo_pairs(negatives, positives, min_chosen_chars=8)
        self.assertEqual(len(pairs), 1)
        self.assertIn("RBAC", pairs[0]["chosen"])
        self.assertIn("Removed all auth", pairs[0]["rejected"])

    def test_skips_when_no_matching_positive(self) -> None:
        negatives = [{"instruction": "Only negative", "rejected": "bad output here"}]
        positives = [{"instruction": "Other task", "output": "good output here"}]
        pairs = build_dpo_pairs(negatives, positives, min_chosen_chars=8)
        self.assertEqual(pairs, [])

    def test_validate_dpo_rows_detects_invalid_pairs(self) -> None:
        contract = validate_dpo_rows(
            [
                {"instruction": "Fix auth", "chosen": "Use RBAC", "rejected": "Use RBAC"},
                {"instruction": "A", "chosen": "B", "rejected": "C"},
            ],
            min_text_chars=4,
        )
        self.assertFalse(contract["valid"])
        self.assertGreaterEqual(int(contract["invalid_rows"]), 1)


if __name__ == "__main__":
    unittest.main()
