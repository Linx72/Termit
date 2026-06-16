from __future__ import annotations

import gc
import tempfile
import unittest
import warnings
from pathlib import Path

from app.domain.schemas import AgentRunRequest
from app.services.agent_memory_store import AgentMemoryStore
from app.services.agent_schedule_service import AgentScheduleService
from app.services.embedding_cache import EmbeddingCache
from app.services.media_job_store import MediaJobStore
from app.services.quota_store import QuotaStore
from app.services.response_cache_store import ResponseCacheStore
from app.services.sqlite_agent_run_store import SQLiteAgentRunStore
from app.services.sqlite_memory_store import SQLiteMemoryStore
from app.services.sqlite_task_store import SQLiteTaskStore
from app.services.trace_span_store import TraceSpanStore


class TestSQLiteResourceWarnings(unittest.TestCase):
    def _collect_sqlite_resource_warnings(self, builder) -> list[warnings.WarningMessage]:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            builder()
            gc.collect()
        return [
            item
            for item in caught
            if issubclass(item.category, ResourceWarning) and "sqlite" in str(item.message).lower()
        ]

    def test_stores_do_not_emit_sqlite_resource_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def _build() -> None:
                task_store = SQLiteTaskStore(str(root / "tasks.db"))
                memory_store = SQLiteMemoryStore(str(root / "memory.db"))
                run_store = SQLiteAgentRunStore(str(root / "runs.db"))
                span_store = TraceSpanStore(str(root / "spans.db"))
                quota_store = QuotaStore(str(root / "quota.db"))
                agent_memory_store = AgentMemoryStore(str(root / "agent_memory.db"))
                response_cache = ResponseCacheStore(
                    backend="sqlite",
                    sqlite_path=str(root / "response_cache.db"),
                )
                embedding_cache = EmbeddingCache(str(root / "embedding_cache.db"))
                media_job_store = MediaJobStore(str(root / "media_jobs.db"))
                schedule_service = AgentScheduleService(
                    str(root / "agent_schedules.db"),
                    enqueue_fn=lambda _agent_id, _payload: "run-test",
                )

                # Touch basic operations to cover read/write paths with sqlite connections.
                memory_store.get("session-a")
                quota_store.get_usage("dev-key")
                agent_memory_store.get_context("agent-a")
                response_cache.set("k", "v", ttl_seconds=60)
                response_cache.get("k")
                embedding_cache.count()
                media_job = media_job_store.create(
                    job_type="image",
                    provider="stub",
                    payload={"prompt": "test"},
                )
                media_job_store.get(media_job.job_id)
                schedule_service.create_schedule(
                    agent_id="agent-a",
                    cron="*/5",
                    payload=AgentRunRequest(input="run schedule"),
                )
                schedule_service.list_schedules()

                del task_store
                del memory_store
                del run_store
                del span_store
                del quota_store
                del agent_memory_store
                del response_cache
                del embedding_cache
                del media_job_store
                del schedule_service

            warnings_found = self._collect_sqlite_resource_warnings(_build)
            self.assertEqual(warnings_found, [])
