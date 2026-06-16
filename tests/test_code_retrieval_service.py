import unittest

from app.services.code_retrieval_service import CodeChunk, CodeRetrievalService


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

    def test_stats_include_mode(self) -> None:
        service = CodeRetrievalService(root_path=".", mode="keyword")
        service.reindex()
        stats = service.stats()
        self.assertEqual(stats["mode"], "keyword")
        self.assertIn("cached_embeddings", stats)

    def test_semantic_mode_falls_back_to_keyword(self) -> None:
        service = CodeRetrievalService(
            root_path=".",
            mode="semantic",
            ollama_base_url="http://127.0.0.1:1",
        )
        service.reindex()
        hits = service.search("ChatService context compaction", limit=3, path_prefix="app/")
        self.assertGreaterEqual(len(hits), 1)

    def test_semantic_search_limits_candidates_with_keyword_prefilter(self) -> None:
        service = CodeRetrievalService(root_path=".", mode="semantic")
        filler = [
            CodeChunk(
                path=f"docs/generated/file_{idx}.md",
                line_start=1,
                line_end=1,
                content="generated placeholder chunk",
            )
            for idx in range(300)
        ]
        target = CodeChunk(
            path="app/middleware/auth_quota.py",
            line_start=1,
            line_end=20,
            content="auth middleware api key quota",
        )
        service._chunks = filler + [target]
        embedded_paths: list[str] = []

        service._embed_text = lambda _text: [1.0, 0.0]  # type: ignore[method-assign]

        def _fake_chunk_embedding(chunk: CodeChunk) -> list[float]:
            embedded_paths.append(chunk.path)
            if "auth_quota" in chunk.path:
                return [1.0, 0.0]
            return [0.0, 1.0]

        service._chunk_embedding = _fake_chunk_embedding  # type: ignore[method-assign]

        hits = service.search("auth middleware api key quota", limit=3)
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("auth_quota", hits[0].path)
        self.assertLessEqual(len(embedded_paths), service._SEMANTIC_MAX_CANDIDATES)

    def test_semantic_search_disables_on_repeated_embedding_failures(self) -> None:
        service = CodeRetrievalService(root_path=".", mode="semantic")
        service._chunks = [
            CodeChunk(path=f"app/services/failure_{idx}.py", line_start=1, line_end=2, content="auth")
            for idx in range(10)
        ]
        service._embed_text = lambda _text: [1.0, 0.0]  # type: ignore[method-assign]
        service._chunk_embedding = lambda _chunk: None  # type: ignore[method-assign]

        hits = service.search("auth middleware", limit=5)
        self.assertGreaterEqual(len(hits), 1)
        self.assertFalse(service._semantic_available)


if __name__ == "__main__":
    unittest.main()
