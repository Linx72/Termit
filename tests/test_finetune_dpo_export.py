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

    def test_uses_embedded_chosen_on_negative(self) -> None:
        negatives = [
            {
                "instruction": "Revert patch",
                "rejected": "User reverted the patch.",
                "chosen": "Applied patch with tests and verify command.",
            }
        ]
        pairs = build_dpo_pairs(negatives, [], min_chosen_chars=8)
        self.assertEqual(len(pairs), 1)
        self.assertIn("verify command", pairs[0]["chosen"])

    def test_pairs_by_run_id(self) -> None:
        negatives = [
            {
                "instruction": "Fix verify resolver",
                "rejected": "verify failed due to cwd mismatch",
                "run_id": "run-42",
            }
        ]
        positives = [
            {
                "instruction": "Different wording",
                "output": "Resolved verify command from project root.",
                "run_id": "run-42",
            }
        ]
        pairs = build_dpo_pairs(negatives, positives, min_chosen_chars=8)
        self.assertEqual(len(pairs), 1)
        self.assertIn("project root", pairs[0]["chosen"])

    def test_pairs_by_instruction_token_overlap(self) -> None:
        negatives = [
            {
                "instruction": "Fix middleware auth for admin routes",
                "rejected": "Removed all auth checks entirely.",
            }
        ]
        positives = [
            {
                "instruction": "Harden middleware auth on admin routes",
                "output": "Added RBAC decorator for admin routes.",
            }
        ]
        pairs = build_dpo_pairs(negatives, positives, min_chosen_chars=8)
        self.assertEqual(len(pairs), 1)
        self.assertIn("RBAC", pairs[0]["chosen"])

    def test_category_fallback_pairs_tool_loop_negative(self) -> None:
        negatives = [
            {
                "instruction": "Long builder prompt unrelated to positives",
                "rejected": "Tool verify failed because cwd was wrong.",
                "category": "tool_loop_negative",
            }
        ]
        positives = [
            {
                "instruction": "Coding task",
                "output": "Applied patch and resolved verify command from repo root.",
                "category": "tool_loop",
            }
        ]
        pairs = build_dpo_pairs(negatives, positives, min_chosen_chars=8)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["source"], "dpo_category_fallback")

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
