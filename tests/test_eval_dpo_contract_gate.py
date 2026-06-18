"""Tests for DPO contract gate CLI."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class EvalDpoContractGateTests(unittest.TestCase):
    def test_gate_passes_valid_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "pairs.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "instruction": "Fix auth middleware",
                        "chosen": "Add RBAC check before handler.",
                        "rejected": "Remove all authentication.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "python3",
                    "scripts/eval_dpo_contract_gate.py",
                    "--dataset",
                    str(dataset),
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("contract gate passed", proc.stdout)

    def test_gate_fails_same_chosen_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "bad.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "instruction": "Fix bug",
                        "chosen": "same answer",
                        "rejected": "same answer",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "python3",
                    "scripts/eval_dpo_contract_gate.py",
                    "--dataset",
                    str(dataset),
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
