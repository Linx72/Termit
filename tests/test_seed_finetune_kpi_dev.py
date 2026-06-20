"""Тесты seed_finetune_kpi_dev.py."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeedFinetuneKpiDevTests(unittest.TestCase):
    def test_seed_writes_passing_kpi(self) -> None:
        python_bin = ROOT / ".venv/bin/python"
        if not python_bin.exists():
            python_bin = Path("python3")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "eval_kpi_last.json"
            proc = subprocess.run(
                [
                    str(python_bin),
                    str(ROOT / "scripts/seed_finetune_kpi_dev.py"),
                    "--force",
                    "--output",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=ROOT,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("kpi_passed"))
            self.assertTrue(payload.get("dev_only"))

    def test_refuses_without_flag(self) -> None:
        python_bin = ROOT / ".venv/bin/python"
        if not python_bin.exists():
            python_bin = Path("python3")
        proc = subprocess.run(
            [str(python_bin), str(ROOT / "scripts/seed_finetune_kpi_dev.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
            env={k: v for k, v in os.environ.items() if k != "TERMIT_FINETUNE_KPI_DEV_SEED"},
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
