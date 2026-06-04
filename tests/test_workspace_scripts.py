from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.workspace_scripts import (
    resolve_dev_server_command,
    resolve_verify_command,
    workspace_script_hints,
)


class WorkspaceScriptsTests(unittest.TestCase):
    def test_npm_verify_chains_test_lint_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "test": "vitest run",
                            "lint": "eslint .",
                            "build": "vite build",
                            "dev": "vite",
                        }
                    }
                ),
                encoding="utf-8",
            )
            cmd = resolve_verify_command(str(root), "")
            self.assertIn("npm test", cmd)
            self.assertIn("npm run lint", cmd)
            self.assertIn("npm run build", cmd)
            self.assertEqual(resolve_dev_server_command(str(root)), "npm run dev")

    def test_workspace_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"dev": "vite", "test": "vitest"}}),
                encoding="utf-8",
            )
            hints = workspace_script_hints(str(root))
            self.assertEqual(hints.get("dev"), "npm run dev")
            self.assertIn("npm test", hints.get("verify", ""))
