from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.domain.schemas import AgentProfileResponse, AgentRunRequest, ChatMessage, ChatRequest, TaskType
from app.services.agent_prompt_cache_service import AgentPromptCacheService
from app.services.agent_tool_schema import (
    build_openai_tools,
    expand_tools_after_use,
    select_initial_tool_names,
)
from app.services.chat_service import ChatService
from app.services.context_packing_service import ContextPackingService
from app.services.model_router import ModelRouter
from tests.test_chat_service import build_router


class HarnessAxisBTests(unittest.TestCase):
    def test_lazy_tools_start_with_core_only(self) -> None:
        enabled = [
            "list_files",
            "read_file",
            "apply_patch",
            "execute_command",
            "generate_image",
        ]
        initial = select_initial_tool_names(enabled, "explain how auth works")
        self.assertEqual(initial, ["list_files", "read_file"])
        self.assertLess(
            len(build_openai_tools(initial)),
            len(build_openai_tools(enabled)),
        )

    def test_lazy_tools_include_mutate_for_file_task(self) -> None:
        enabled = ["list_files", "read_file", "apply_patch", "execute_command"]
        initial = select_initial_tool_names(enabled, "fix bug and apply patch to main.py")
        self.assertIn("apply_patch", initial)
        self.assertIn("execute_command", initial)

    def test_expand_tools_after_read_file(self) -> None:
        enabled = ["list_files", "read_file", "apply_patch", "execute_command"]
        active = set(select_initial_tool_names(enabled, "explain code"))
        expanded = expand_tools_after_use("read_file", enabled, active)
        self.assertIn("apply_patch", expanded)
        self.assertIn("execute_command", expanded)

    def test_prompt_cache_hit(self) -> None:
        cache = AgentPromptCacheService(ttl_seconds=60)
        key = AgentPromptCacheService.enrichment_key(
            agent_id="a1",
            path_prefix="app",
            instruction="fix bug",
            changed_files=["app/main.py"],
        )
        cache.put(key, ["line1", "line2"])
        self.assertEqual(cache.get(key), ["line1", "line2"])

    def test_pack_incremental_skips_seen_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.py"
            second = root / "b.py"
            first.write_text("a = 1\n", encoding="utf-8")
            second.write_text("b = 2\n", encoding="utf-8")
            service = ContextPackingService(str(root))
            packed1, seen = service.pack_incremental(
                query="update",
                changed_files=["a.py", "b.py"],
                seen_paths=set(),
                retrieval=None,
                symbol_index=None,
                include_retrieval=False,
            )
            self.assertIn("a.py", packed1)
            self.assertIn("b.py", packed1)
            packed2, seen2 = service.pack_incremental(
                query="update more",
                changed_files=["a.py", "b.py", "c.py"],
                seen_paths=seen,
                retrieval=None,
                symbol_index=None,
                include_retrieval=False,
            )
            self.assertNotIn("a.py", packed2)
            self.assertNotIn("b.py", packed2)
            self.assertIn("c.py", seen2)

    def test_chat_skips_enrichment_when_flag_set(self) -> None:
        router = build_router()
        enrichment = MagicMock()
        enrichment.build_system_messages.return_value = [
            ChatMessage(role="system", content="SHOULD NOT APPEAR")
        ]
        provider = MagicMock()
        provider.generate = AsyncMock(return_value='{"action":"final","answer":"ok"}')
        service = ChatService(
            model_router=router,
            providers={"ollama": provider},
            memory_store=MagicMock(),
            context_enrichment=enrichment,
        )
        payload = ChatRequest(
            message="continue",
            task_type=TaskType.coding,
            model="ollama:test",
            use_memory=False,
            skip_context_enrichment=True,
            pin_model=True,
            skip_dual_pass=True,
            history=[
                ChatMessage(role="system", content="stable prefix"),
                ChatMessage(role="user", content="task"),
            ],
        )

        async def _run() -> None:
            await service.chat(payload)

        import asyncio

        asyncio.run(_run())
        enrichment.build_system_messages.assert_not_called()
        provider.generate.assert_awaited_once()
        call_kwargs = provider.generate.await_args.kwargs
        self.assertEqual(call_kwargs["model_name"], "ollama:test")


if __name__ == "__main__":
    unittest.main()
