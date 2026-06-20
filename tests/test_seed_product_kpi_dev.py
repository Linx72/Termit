"""Тесты seed_product_kpi_dev.py."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeedProductKpiDevTests(unittest.TestCase):
    def test_seed_improves_tool_loop_window_with_force(self) -> None:
        python_bin = ROOT / ".venv/bin/python"
        if not python_bin.exists():
            python_bin = Path("python3")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "agent_runs.db"
            desktop_dir = Path(tmp) / "desktop"
            env = {
                **os.environ,
                "TERMIT_AGENT_RUN_SQLITE_PATH": str(db_path),
                "TERMIT_DESKTOP_STATE_DIR": str(desktop_dir),
            }
            proc = subprocess.run(
                [
                    str(python_bin),
                    str(ROOT / "scripts/seed_product_kpi_dev.py"),
                    "--force",
                    "--runs",
                    "6",
                    "--chats",
                    "0",
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=ROOT,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            start = proc.stdout.find("{")
            end = proc.stdout.rfind("}")
            summary = json.loads(proc.stdout[start : end + 1])
            window = summary.get("tool_loop_window", {})
            self.assertGreaterEqual(float(window.get("completion", 0)), 0.8)
            self.assertGreaterEqual(float(window.get("success", 0)), 0.8)

    def test_refuses_without_flag(self) -> None:
        python_bin = ROOT / ".venv/bin/python"
        if not python_bin.exists():
            python_bin = Path("python3")
        proc = subprocess.run(
            [str(python_bin), str(ROOT / "scripts/seed_product_kpi_dev.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
