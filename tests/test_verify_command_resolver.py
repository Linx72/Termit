import tempfile
import unittest
from pathlib import Path

from app.services.verify_command_resolver import resolve_verify_command


class VerifyCommandResolverTests(unittest.TestCase):
    def test_explicit_command_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(resolve_verify_command(tmp, "make test"), "make test")

    def test_python_repo_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            cmd = resolve_verify_command(tmp, "")
            self.assertIn("unittest", cmd)

    def test_node_repo_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text("{}", encoding="utf-8")
            cmd = resolve_verify_command(tmp, "")
            self.assertIn("npm test", cmd)

    def test_unknown_repo_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(resolve_verify_command(tmp, ""), "")


if __name__ == "__main__":
    unittest.main()
