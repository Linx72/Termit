"""Тесты seed_beta_cohort_dev.py."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeedBetaCohortDevTests(unittest.TestCase):
    def test_seed_increases_cohort_with_force(self) -> None:
        python_bin = ROOT / ".venv/bin/python"
        if not python_bin.exists():
            python_bin = Path("python3")
        with tempfile.TemporaryDirectory() as tmp:
            feedback_path = Path(tmp) / "feedback.jsonl"
            env = {**os.environ, "TERMIT_FEEDBACK_FILE": str(feedback_path)}
            proc = subprocess.run(
                [
                    str(python_bin),
                    str(ROOT / "scripts/seed_beta_cohort_dev.py"),
                    "--force",
                    "--actors",
                    "6",
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=ROOT,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(feedback_path.is_file())
            lines = feedback_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 6)
            start = proc.stdout.find("{")
            end = proc.stdout.rfind("}")
            self.assertGreater(start, -1)
            metrics = json.loads(proc.stdout[start : end + 1])
            self.assertGreaterEqual(metrics.get("cohort_size_d30", 0), 5)

    def test_refuses_without_flag(self) -> None:
        python_bin = ROOT / ".venv/bin/python"
        if not python_bin.exists():
            python_bin = Path("python3")
        proc = subprocess.run(
            [str(python_bin), str(ROOT / "scripts/seed_beta_cohort_dev.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
