import unittest

from app.services.code_retrieval_service import CodeRetrievalService


class CodeRetrievalServiceTests(unittest.TestCase):
    def test_indexes_and_finds_chat_service_symbol(self) -> None:
        service = CodeRetrievalService(root_path=".")
        indexed_files, indexed_chunks = service.reindex()
        self.assertGreater(indexed_files, 5)
        self.assertGreater(indexed_chunks, 10)

        hits = service.search("ChatService context compaction", limit=5, path_prefix="app/")
        self.assertGreaterEqual(len(hits), 1)
        paths = {item.path for item in hits}
        self.assertTrue(
            any(
                "chat_service" in path or "context_compaction" in path
                for path in paths
            )
        )

    def test_path_prefix_filter(self) -> None:
        service = CodeRetrievalService(root_path=".")
        service.reindex()
        hits = service.search("TaskService", limit=5, path_prefix="app/services/task")
        self.assertGreaterEqual(len(hits), 1)
        for item in hits:
            self.assertTrue(item.path.startswith("app/services/task"))


if __name__ == "__main__":
    unittest.main()
