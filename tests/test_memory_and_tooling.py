import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import (
    ApplyPatchHunk,
    ApplyPatchRequest,
    ChatMessage,
    ExecuteCommandRequest,
    ListFilesRequest,
    ReadFileRequest,
    ToolRiskLevel,
)
from app.services.memory_store import MemoryStore
from app.services.tooling_service import ToolingError, ToolingService


class MemoryStoreTests(unittest.TestCase):
    def test_memory_store_truncates_old_messages(self) -> None:
        store = MemoryStore(max_messages_per_session=2)
        store.append("s1", ChatMessage(role="user", content="1"))
        store.append("s1", ChatMessage(role="assistant", content="2"))
        store.append("s1", ChatMessage(role="user", content="3"))
        history = store.get("s1")
        self.assertEqual([m.content for m in history], ["2", "3"])

    def test_memory_store_clear(self) -> None:
        store = MemoryStore()
        store.append("s2", ChatMessage(role="user", content="x"))
        self.assertTrue(store.clear("s2"))
        self.assertFalse(store.clear("s2"))


class ToolingServiceTests(unittest.TestCase):
    def test_read_file_blocks_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ToolingService(str(root))
            with self.assertRaises(ToolingError):
                service.read_file(ReadFileRequest(path="../secret.txt"))

    def test_list_files_in_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("print('x')", encoding="utf-8")
            (root / "b.txt").write_text("ok", encoding="utf-8")
            service = ToolingService(str(root))
            resp = service.list_files(ListFilesRequest(path=".", pattern="*.py"))
            self.assertEqual(resp.files, ["a.py"])

    def test_execute_command_blocks_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = ToolingService(tmp)
            resp = service.execute_command(
                ExecuteCommandRequest(command="rm -rf /", path=".")
            )
            self.assertFalse(resp.executed)
            self.assertEqual(resp.risk_level, ToolRiskLevel.blocked)
            audit = service.get_audit_events(limit=1)
            self.assertEqual(audit[0].action, "policy_block")

    def test_execute_command_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = ToolingService(tmp)
            resp = service.execute_command(
                ExecuteCommandRequest(command="git status", path=".")
            )
            self.assertFalse(resp.executed)
            self.assertTrue(resp.requires_confirmation)
            self.assertEqual(resp.risk_level, ToolRiskLevel.confirm)

    def test_execute_command_runs_safe_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = ToolingService(tmp)
            resp = service.execute_command(
                ExecuteCommandRequest(command="python3 -c \"print('ok')\"", path=".")
            )
            self.assertTrue(resp.executed)
            self.assertEqual(resp.exit_code, 0)
            self.assertIn("ok", resp.stdout)
            self.assertEqual(resp.risk_level, ToolRiskLevel.safe)
            self.assertTrue(root.exists())

    def test_execute_command_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            flag_path = Path(tmp) / "flag.txt"
            service = ToolingService(tmp)
            cmd = f"python3 -c \"open(r'{str(flag_path)}','w').write('x')\""
            resp = service.execute_command(
                ExecuteCommandRequest(
                    command=cmd,
                    path=".",
                    dry_run=True,
                    confirmed=True,
                )
            )
            self.assertFalse(resp.executed)
            self.assertFalse(flag_path.exists())
            audit = service.get_audit_events(limit=1)
            self.assertEqual(audit[0].action, "dry_run")

    def test_apply_patch_blocks_sensitive_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = ToolingService(tmp)
            resp = service.apply_patch(
                ApplyPatchRequest(path=".env", content="SECRET=1", create=True)
            )
            self.assertFalse(resp.applied)
            self.assertEqual(resp.risk_level, ToolRiskLevel.blocked)

    def test_apply_patch_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "example.py"
            target.write_text("print('old')\n", encoding="utf-8")
            service = ToolingService(tmp)
            resp = service.apply_patch(
                ApplyPatchRequest(
                    path="example.py",
                    hunks=[ApplyPatchHunk(old_text="old", new_text="new")],
                )
            )
            self.assertFalse(resp.applied)
            self.assertTrue(resp.requires_confirmation)
            self.assertEqual(target.read_text(encoding="utf-8"), "print('old')\n")

    def test_apply_patch_applies_hunks_when_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "example.py"
            target.write_text("print('old')\n", encoding="utf-8")
            service = ToolingService(tmp)
            resp = service.apply_patch(
                ApplyPatchRequest(
                    path="example.py",
                    hunks=[ApplyPatchHunk(old_text="old", new_text="new")],
                    confirmed=True,
                )
            )
            self.assertTrue(resp.applied)
            self.assertEqual(resp.hunks_applied, 1)
            self.assertIn("new", target.read_text(encoding="utf-8"))

    def test_apply_patch_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "new.py"
            service = ToolingService(tmp)
            resp = service.apply_patch(
                ApplyPatchRequest(
                    path="new.py",
                    content="print('created')\n",
                    create=True,
                    confirmed=True,
                )
            )
            self.assertTrue(resp.applied)
            self.assertTrue(resp.created)
            self.assertTrue(target.exists())
            self.assertIn("created", target.read_text(encoding="utf-8"))

    def test_apply_patch_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "example.py"
            target.write_text("alpha\n", encoding="utf-8")
            service = ToolingService(tmp)
            resp = service.apply_patch(
                ApplyPatchRequest(
                    path="example.py",
                    content="beta\n",
                    dry_run=True,
                )
            )
            self.assertFalse(resp.applied)
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha\n")
            self.assertIn("beta", resp.preview_excerpt)


if __name__ == "__main__":
    unittest.main()
