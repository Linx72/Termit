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
                    "--local-runs",
                    "10",
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
            self.assertTrue(summary.get("kpi_overall_passed"))

    def test_writes_chat_metrics_seed_file(self) -> None:
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
                    "--local-runs",
                    "0",
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
            seed_file = desktop_dir / "dev_chat_metrics_seed.json"
            self.assertTrue(seed_file.is_file())
            payload = json.loads(seed_file.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("dev_only"))
            self.assertGreaterEqual(len(payload.get("chat_latencies_ms", [])), 5)

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
