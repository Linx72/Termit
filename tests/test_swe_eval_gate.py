"""Тесты scripts/swe_eval_gate.py."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SweEvalGateTests(unittest.TestCase):
    def test_swe_gate_passes_all_fixtures(self) -> None:
        python_bin = ROOT / ".venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path("python3")
        proc = subprocess.run(
            [str(python_bin), str(ROOT / "scripts" / "swe_eval_gate.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        stdout = proc.stdout
        start = stdout.index("{")
        end = stdout.rindex("}") + 1
        payload = json.loads(stdout[start:end])
        self.assertTrue(payload.get("gate_passed"))
        self.assertGreaterEqual(len(payload.get("scenario_ids", [])), 5)


if __name__ == "__main__":
    unittest.main()
