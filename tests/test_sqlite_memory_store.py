import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import ChatMessage
from app.services.sqlite_memory_store import SQLiteMemoryStore


class SQLiteMemoryStoreTests(unittest.TestCase):
    def test_persists_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "memory.db")
            store = SQLiteMemoryStore(db_path=db_path, max_messages_per_session=10)
            store.append("sess1", ChatMessage(role="user", content="hello"))
            store.append("sess1", ChatMessage(role="assistant", content="world"))

            history = store.get("sess1")
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0].content, "hello")
            self.assertEqual(history[1].content, "world")

    def test_truncates_by_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "memory.db")
            store = SQLiteMemoryStore(db_path=db_path, max_messages_per_session=2)
            store.append("sess2", ChatMessage(role="user", content="1"))
            store.append("sess2", ChatMessage(role="assistant", content="2"))
            store.append("sess2", ChatMessage(role="user", content="3"))

            history = store.get("sess2")
            self.assertEqual([m.content for m in history], ["2", "3"])

    def test_clear_returns_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "memory.db")
            store = SQLiteMemoryStore(db_path=db_path, max_messages_per_session=10)
            store.append("sess3", ChatMessage(role="user", content="x"))
            self.assertTrue(store.clear("sess3"))
            self.assertFalse(store.clear("sess3"))


if __name__ == "__main__":
    unittest.main()
