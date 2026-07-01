from __future__ import annotations

import json
import logging
import uuid
import asyncio

_logger = logging.getLogger("termit.chat_service")

from time import time
from typing import AsyncIterator, Optional

from app.domain.exceptions import GuardrailBlockedError
from app.domain.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FimCompletionRequest,
    FimCompletionResponse,
    ProviderInfo,
    ProviderStatus,
    TaskType,
)
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.context_compaction import ContextCompactor
from app.services.context_enrichment_service import ContextEnrichmentService
from app.services.guardrail_service import GuardrailService
from app.services.memory_store import MemoryBackend
from app.services.model_router import ModelRouter
from app.services.provider_circuit_breaker import ProviderCircuitBreaker
from app.services.providers.base import (
    BaseProvider,
    ProviderError,
    ProviderStreamChunk,
    ProviderToolCall,
    ProviderToolResponse,
)
from app.services.response_cache_store import ResponseCacheStore
from app.services.telemetry_store import TelemetryStore
from app.services.tooling_service import ToolingService
from app.services.playwright_browser_service import PlaywrightBrowserService
from app.services.playwright_browser_service import PlaywrightUnavailableError


from dataclasses import dataclass, field


@dataclass
class ToolStepChatResult:
    provider: str
    model: str
    content: str
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    attempted_models: list[str] = field(default_factory=list)


class ChatService:
    """Чат-сервис TermitPro с поддержкой SSE-стриминга и native tool calling."""

    def __init__(
        self,
        model_router: ModelRouter,
        providers: dict[str, BaseProvider],
        memory_store: MemoryBackend,
        circuit_breaker: Optional[ProviderCircuitBreaker] = None,
        cache_ttl_seconds: int = 120,
        response_cache: Optional[ResponseCacheStore] = None,
        telemetry: Optional[TelemetryStore] = None,
        context_compactor: Optional[ContextCompactor] = None,
        code_retrieval: Optional[CodeRetrievalService] = None,
        context_enrichment: Optional[ContextEnrichmentService] = None,
        retrieval_enabled: bool = True,
        provider_retry_attempts: int = 2,
        provider_retry_backoff_ms: int = 150,
        dual_pass_enabled: bool = False,
        dual_pass_task_types: str = "coding,review,debug",
        tooling_service: Optional[ToolingService] = None,
        guardrail: Optional["GuardrailService"] = None,
        browser: Optional[PlaywrightBrowserService] = None,
    ) -> None:
        self.model_router = model_router
        self.providers = providers
        self.memory_store = memory_store
        self.circuit_breaker = circuit_breaker
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        if response_cache is not None:
            self.response_cache = response_cache
        elif self.cache_ttl_seconds > 0:
            self.response_cache = ResponseCacheStore(backend="memory")
        else:
            self.response_cache = None
        self.telemetry = telemetry
        self._compactor = context_compactor or ContextCompactor()
        self._retrieval = code_retrieval
        self._enrichment = context_enrichment
        self._retrieval_enabled = retrieval_enabled
        self._provider_retry_attempts = max(1, provider_retry_attempts)
        self._provider_retry_backoff_ms = max(0, provider_retry_backoff_ms)
        self._dual_pass_enabled = dual_pass_enabled
        self._dual_pass_task_types = {
            item.strip().lower()
            for item in dual_pass_task_types.split(",")
            if item.strip()
        }
        self._tooling = tooling_service
        self._guardrail = guardrail
        self._browser = browser

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        started_at = time()
        session_id = payload.session_id
        if payload.use_memory and not session_id:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        messages = list(payload.history)
        if payload.use_memory and session_id:
            messages.extend(self.memory_store.get(session_id))
        messages.append(ChatMessage(role="user", content=payload.message))

        # Safety guardrail — block prompts with secrets/credentials before
        # they reach an LLM, even in compacted form.
        if self._guardrail:
            result = self._guardrail.check_prompt(payload.message)
            if not result.allowed:
                raise GuardrailBlockedError()

        compaction = self._compactor.compact(messages)
        messages = list(compaction.messages)
        retrieval_hits = 0
        if not payload.skip_context_enrichment and self._enrichment is not None:
            enrichment_messages = await self._enrichment.build_system_messages(payload)
            if enrichment_messages:
                messages = enrichment_messages + messages
            if payload.use_retrieval and self._retrieval_enabled and self._retrieval is not None:
                hits = self._retrieval.search(
                    payload.message,
                    limit=payload.retrieval_limit,
                    path_prefix=payload.retrieval_path_prefix,
                )
                retrieval_hits = len(hits)
        elif (
            not payload.skip_context_enrichment
            and payload.use_retrieval
            and self._retrieval_enabled
            and self._retrieval is not None
        ):
            hits = self._retrieval.search(
                payload.message,
                limit=payload.retrieval_limit,
                path_prefix=payload.retrieval_path_prefix,
            )
            retrieval_hits = len(hits)
            if hits:
                context_body = ContextCompactor.format_retrieval_context(
                    [(item.path, item.excerpt, item.score) for item in hits]
                )
                messages.insert(
                    0,
                    ChatMessage(role="system", content=context_body),
                )

        candidate_models = self.model_router.candidate_models(
            payload.task_type,
            payload.model,
            message=payload.message,
            history=messages,
            repo_profile=payload.repo_profile,
            path_prefix=payload.retrieval_path_prefix,
            routing_policy=payload.routing_policy,
        )
        if payload.pin_model and payload.model:
            candidate_models = [payload.model]
        selected_via = payload.routing_policy
        if payload.repo_profile:
            selected_via = f"repo_profile:{payload.repo_profile}"
        elif payload.routing_policy == "benchmark":
            selected_via = "benchmark"

        cache_key = self._build_cache_key(payload, messages, candidate_models)
        if not payload.use_memory:
            cached = self._get_cached(cache_key)
            if cached is not None:
                cached.history_size = len(messages)
                self._record_chat_telemetry(
                    started_at=started_at,
                    success=True,
                    cache_hit=True,
                    selected_model=cached.model,
                    response_text=cached.response,
                    fallback_used=len(cached.attempted_models) > 1,
                )
                return cached

        attempted_models: list[str] = []
        response_text = ""
        selected_model = ""
        selected_provider = ""
        errors: list[str] = []

        for model_name in candidate_models:
            provider_name = self.model_router.provider_for_model(model_name)
            provider = self.providers.get(provider_name)
            attempted_models.append(model_name)

            if provider is None:
                errors.append(
                    f"Provider '{provider_name}' is not configured for model '{model_name}'."
                )
                continue

            if self.circuit_breaker and not self.circuit_breaker.is_available(provider_name):
                errors.append(f"Provider '{provider_name}' circuit is open.")
                continue

            try:
                response_text = await self._generate_with_retries(
                    provider=provider,
                    model_name=model_name,
                    messages=messages,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                )
                selected_model = model_name
                selected_provider = provider_name
                if self.circuit_breaker:
                    self.circuit_breaker.record_success(provider_name)
                break
            except ProviderError as exc:
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(provider_name)
                errors.append(str(exc))

        if not selected_model:
            self._record_chat_telemetry(
                started_at=started_at,
                success=False,
                cache_hit=False,
                selected_model=None,
                response_text="",
                fallback_used=False,
            )
            raise ProviderError(" | ".join(errors) if errors else "No available models.")

        validator_model: Optional[str] = None
        if (
            not payload.skip_dual_pass
            and self._dual_pass_enabled
            and payload.task_type.value in self._dual_pass_task_types
        ):
            response_text, validator_model = await self._apply_dual_pass(
                payload=payload,
                draft=response_text,
                draft_model=selected_model,
            )

        if payload.use_memory and session_id:
            self.memory_store.append(session_id, ChatMessage(role="user", content=payload.message))
            self.memory_store.append(session_id, ChatMessage(role="assistant", content=response_text))

        response = ChatResponse(
            provider=selected_provider,
            model=selected_model,
            task_type=payload.task_type,
            session_id=session_id,
            history_size=len(messages),
            attempted_models=attempted_models,
            response=response_text,
            context_compacted=compaction.compacted,
            dropped_messages=compaction.dropped_messages,
            retrieval_hits=retrieval_hits,
            repo_profile=payload.repo_profile,
            routing_policy=payload.routing_policy,
            selected_via=selected_via,
            dual_pass_used=validator_model is not None,
            validator_model=validator_model,
        )
        if not payload.use_memory:
            self._set_cached(cache_key, response)
        self._record_chat_telemetry(
            started_at=started_at,
            success=True,
            cache_hit=False,
            selected_model=selected_model,
            response_text=response_text,
            fallback_used=bool(attempted_models and selected_model != attempted_models[0]),
        )
        return response

    # ── Chat Stream (реальный SSE-стриминг + tool calling) ───────────────────

    async def chat_stream(self, payload: ChatRequest) -> AsyncIterator[str]:
        """
        Настоящий SSE-стриминг: токены отдаются по мере генерации LLM.
        
        Поддерживает:
        - Инкрементальные текстовые токены (event: token)
        - Reasoning-токены для DeepSeek R1 (event: reasoning)
        - Native tool calling с циклом: model → tool_call → tool_result → model
        - Прогресс инструментов (event: tool_progress)
        - Мета-информацию (event: meta)
        - Предупреждения (event: warning)
        - Завершение (event: done)
        - Ошибки (event: error)
        """
        started_at = time()
        session_id = payload.session_id or f"sess_{uuid.uuid4().hex[:12]}"

        # ── Подготовка сообщений ──
        messages = list(payload.history)
        if payload.use_memory and session_id:
            memory_msgs = self.memory_store.get(session_id)
            messages.extend(memory_msgs)
        messages.append(ChatMessage(role="user", content=payload.message))

        # Контекстная энричмент
        if not payload.skip_context_enrichment and self._enrichment is not None:
            enrichment_messages = await self._enrichment.build_system_messages(payload)
            if enrichment_messages:
                messages = enrichment_messages + messages
            if payload.use_retrieval and self._retrieval_enabled and self._retrieval is not None:
                hits = self._retrieval.search(
                    payload.message,
                    limit=payload.retrieval_limit,
                    path_prefix=payload.retrieval_path_prefix,
                )
                if hits:
                    context_body = ContextCompactor.format_retrieval_context(
                        [(item.path, item.excerpt, item.score) for item in hits]
                    )
                    messages.insert(0, ChatMessage(role="system", content=context_body))

        compaction = self._compactor.compact(messages)
        messages = list(compaction.messages)
        if compaction.compacted:
            yield self._sse_event("warning", {
                "message": f"Контекст сжат: удалено {compaction.dropped_messages} сообщений"
            })

        # ── Выбор модели ──
        candidate_models = self.model_router.candidate_models(
            payload.task_type,
            payload.model,
            message=payload.message,
            history=messages,
            repo_profile=payload.repo_profile,
            path_prefix=payload.retrieval_path_prefix,
            routing_policy=payload.routing_policy,
        )
        if payload.pin_model and payload.model:
            candidate_models = [payload.model]

        # ── Инструменты (если task_type = coding) ──
        tools: list[dict[str, object]] | None = None
        if payload.task_type in {TaskType.coding, TaskType.debug}:
            try:
                from app.services.agent_tool_schema import build_openai_tools, select_initial_tool_names
                tool_names = select_initial_tool_names()
                tools = build_openai_tools(tool_names)
            except Exception:
                _logger.warning("Failed to build tools, proceeding without tools", exc_info=True)
                tools = None

        # ── Проверка кеша ответов (до вызова LLM) ──
        cache_key = self._build_cache_key(payload, messages, candidate_models)
        if not payload.use_memory:
            cached = self._get_cached(cache_key)
            if cached is not None:
                # Эмулируем стриминг — токенизируем кешированный ответ
                full_text = cached.response
                yield self._sse_event("meta", {
                    "provider": cached.provider,
                    "model": cached.model,
                    "session_id": session_id,
                    "history_size": len(messages),
                    "attempted_models": [cached.model],
                    "cached": True,
                })
                # Отдаём кеш chunk'ами по ~50 символов для UI-фидбека
                chunk_size = 50
                for i in range(0, len(full_text), chunk_size):
                    yield self._sse_event("token", {
                        "text": full_text[i:i + chunk_size]
                    })
                yield self._sse_event("done", {
                    "session_id": session_id,
                    "response": full_text,
                    "cached": True,
                })
                self._record_chat_telemetry(
                    started_at=started_at,
                    success=True,
                    cache_hit=True,
                    selected_model=cached.model,
                    response_text=full_text,
                    fallback_used=False,
                )
                return

        # ── Основной цикл: стриминг + tool calling ──
        MAX_TOOL_ROUNDS = 5
        full_text = ""
        selected_model = ""
        selected_provider = ""

        for model_name in candidate_models:
            provider_name = self.model_router.provider_for_model(model_name)
            provider = self.providers.get(provider_name)

            if provider is None:
                continue
            if self.circuit_breaker and not self.circuit_breaker.is_available(provider_name):
                yield self._sse_event("warning", {
                    "message": f"Провайдер {provider_name} недоступен (circuit open)"
                })
                continue

            selected_model = model_name
            selected_provider = provider_name

            yield self._sse_event("meta", {
                "provider": provider_name,
                "model": model_name,
                "session_id": session_id,
                "history_size": len(messages),
                "attempted_models": candidate_models,
            })

            try:
                # ── Tool calling loop ──
                current_messages = list(messages)
                tool_round = 0

                while tool_round < MAX_TOOL_ROUNDS:
                    tool_round += 1
                    chunk_text = ""
                    chunk_tool_calls: list[ProviderToolCall] = []

                    # Стриминг от провайдера
                    async for chunk in provider.generate_stream(
                        model_name=model_name,
                        messages=current_messages,
                        temperature=payload.temperature,
                        max_tokens=payload.max_tokens,
                        tools=tools if tool_round == 1 else tools,  # tools только в первом раунде
                    ):
                        if chunk.token:
                            chunk_text += chunk.token
                            full_text += chunk.token
                            yield self._sse_event("token", {"text": chunk.token})

                        if chunk.reasoning:
                            yield self._sse_event("reasoning", {"text": chunk.reasoning})

                        if chunk.tool_call_delta:
                            chunk_tool_calls.append(chunk.tool_call_delta)

                        if chunk.is_done:
                            break

                    # Если нет tool calls — стриминг завершён
                    if not chunk_tool_calls:
                        break

                    # ── Параллельное выполнение инструментов ──
                    # Уведомляем о старте всех инструментов
                    for tc in chunk_tool_calls:
                        yield self._sse_event("tool_progress", {
                            "event": "start",
                            "name": tc.name,
                            "preview": json.dumps(tc.arguments, ensure_ascii=True)[:200],
                        })

                    # Запускаем все tool calls параллельно
                    async def _run_one(tc: ProviderToolCall) -> tuple[ProviderToolCall, str]:
                        try:
                            result = await self._execute_tool_call(tc)
                        except Exception as exc:
                            result = json.dumps({"error": f"Tool '{tc.name}' failed: {exc}"})
                        return tc, result

                    parallel_tasks = [_run_one(tc) for tc in chunk_tool_calls]
                    tool_results: list[tuple[ProviderToolCall, str]] = await asyncio.gather(
                        *parallel_tasks
                    )

                    for tc, tool_result in tool_results:
                        yield self._sse_event("tool_progress", {
                            "event": "done",
                            "name": tc.name,
                            "preview": tool_result[:200],
                        })

                        # Добавляем результат в диалог
                        current_messages.append(ChatMessage(
                            role="assistant",
                            content=f"Tool call: {tc.name}({json.dumps(tc.arguments)})",
                        ))
                        current_messages.append(ChatMessage(
                            role="tool",
                            content=tool_result,
                        ))

                # ── Успешно ──
                full_text = full_text or chunk_text
                if self.circuit_breaker:
                    self.circuit_breaker.record_success(provider_name)

                # ── RLM Best-of-N retry (при низком качестве) ──
                if getattr(payload, 'rlm_retry', False) and not payload.use_memory:
                    try:
                        from app.services.rlm_best_of_n import RLMBestOfN
                        # Use the fastest model from candidate_models as RLM generator
                        rlm_model = self.model_router.resolve_profile_model("coding-fast") or model_name
                        rlm_provider_name = self.model_router.provider_for_model(rlm_model)
                        rlm_provider = self.providers.get(rlm_provider_name) if rlm_provider_name else provider
                        if rlm_provider:
                            rlm = RLMBestOfN(self, rlm_provider, rlm_model)
                            improved = await rlm.best_of_n(messages, n=3)
                            if improved and len(improved) > len(full_text) * 0.5:
                                full_text = improved
                                yield self._sse_event("rlm_improved", {
                                    "message": "Ответ улучшен через RLM Best-of-N"
                                })
                    except Exception as exc:
                        logger.warning("RLM Best-of-N retry failed: %s", exc)

                # Сохраняем в память
                if payload.use_memory and session_id:
                    self.memory_store.append(session_id, ChatMessage(role="user", content=payload.message))
                    self.memory_store.append(session_id, ChatMessage(role="assistant", content=full_text))

                # Сохраняем в кеш ответов (для повторных запросов)
                if not payload.use_memory:
                    response = ChatResponse(
                        provider=selected_provider,
                        model=selected_model,
                        task_type=payload.task_type,
                        session_id=session_id,
                        history_size=len(messages),
                        attempted_models=candidate_models,
                        response=full_text,
                        context_compacted=compaction.compacted,
                        dropped_messages=compaction.dropped_messages,
                        routing_policy=payload.routing_policy,
                        selected_via=payload.routing_policy or "auto",
                    )
                    self._set_cached(cache_key, response)

                yield self._sse_event("done", {
                    "session_id": session_id,
                    "response": full_text,
                })

                self._record_chat_telemetry(
                    started_at=started_at,
                    success=True,
                    cache_hit=False,
                    selected_model=selected_model,
                    response_text=full_text,
                    fallback_used=False,
                )
                return

            except ProviderError as exc:
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(provider_name)
                yield self._sse_event("error", {
                    "error": str(exc),
                    "recommendation": "Попробуйте другую модель или провайдера",
                    "category": "provider",
                    "can_retry": True,
                })
                continue

        # ── Все модели исчерпаны ──
        yield self._sse_event("error", {
            "error": "Все доступные модели вернули ошибку",
            "recommendation": "Проверьте конфигурацию провайдеров",
            "category": "all_providers_failed",
            "can_retry": False,
        })
        yield self._sse_event("done", {})

    async def _execute_tool_call(self, tc: ProviderToolCall) -> str:
        """Выполнить tool call и вернуть результат."""
        if self._tooling is None:
            return json.dumps({"error": "ToolingService не настроен"})

        try:
            if tc.name == "list_files":
                result = self._tooling.list_files_by_pattern(
                    path=tc.arguments.get("path", "."),
                    pattern=tc.arguments.get("pattern", "*"),
                )
                return json.dumps(result, ensure_ascii=True)

            elif tc.name == "read_file":
                result = self._tooling.read_file_content(
                    path=tc.arguments.get("path", "."),
                    file_name=tc.arguments.get("file", ""),
                )
                return json.dumps(result, ensure_ascii=True)

            elif tc.name == "execute_command":
                result = self._tooling.execute_command_dry(
                    command=tc.arguments.get("command", ""),
                    path=tc.arguments.get("path", "."),
                )
                return json.dumps(result, ensure_ascii=True)

            elif tc.name == "apply_patch":
                content = tc.arguments.get("content", "")
                hunks = tc.arguments.get("hunks", [])
                result = self._tooling.apply_patch_dry(
                    path=tc.arguments.get("path", "."),
                    content=str(content) if content else "",
                    hunks=hunks if isinstance(hunks, list) else [],
                )
                return json.dumps(result, ensure_ascii=True)

            # ── Browser-тулы ──
            elif tc.name.startswith("browser_"):
                if self._browser is None or not self._browser.available():
                    return json.dumps({"error": "Playwright browser не доступен"})
                try:
                    if tc.name == "browser_navigate":
                        result = self._browser.navigate(
                            str(tc.arguments.get("url", "")),
                            timeout_seconds=int(tc.arguments.get("timeout_seconds", 30)),
                            wait_until=str(tc.arguments.get("wait_until", "domcontentloaded")),
                        )
                    elif tc.name == "browser_get_page_state":
                        result = self._browser.get_page_state(
                            include_html=bool(tc.arguments.get("include_html", False)),
                            max_elements=int(tc.arguments.get("max_elements", 50)),
                        )
                    elif tc.name == "browser_click":
                        result = self._browser.click(
                            selector=str(tc.arguments.get("selector", "")),
                            text=str(tc.arguments.get("text", "")),
                            index=tc.arguments.get("index"),
                            confirmed=bool(tc.arguments.get("confirmed", False)),
                        )
                    elif tc.name == "browser_fill":
                        result = self._browser.fill(
                            selector=str(tc.arguments.get("selector", "")),
                            value=str(tc.arguments.get("value", "")),
                            index=tc.arguments.get("index"),
                            clear_first=bool(tc.arguments.get("clear_first", True)),
                        )
                    elif tc.name == "browser_get_text":
                        result = self._browser.get_text(
                            selector=str(tc.arguments.get("selector", "")),
                            max_chars=int(tc.arguments.get("max_chars", 10000)),
                        )
                    elif tc.name == "browser_screenshot":
                        result = self._browser.screenshot(
                            selector=str(tc.arguments.get("selector", "")),
                            full_page=bool(tc.arguments.get("full_page", False)),
                            project_id=str(tc.arguments.get("project_id", "")),
                        )
                    elif tc.name == "browser_evaluate_js":
                        result = self._browser.evaluate_js(
                            str(tc.arguments.get("expression", "")),
                        )
                    elif tc.name == "browser_wait_for":
                        result = self._browser.wait_for(
                            selector=str(tc.arguments.get("selector", "")),
                            state=str(tc.arguments.get("state", "visible")),
                            timeout_seconds=int(tc.arguments.get("timeout_seconds", 10)),
                        )
                    elif tc.name == "browser_smart_login":
                        result = self._browser.smart_login(
                            url=str(tc.arguments.get("url", "")),
                            username=str(tc.arguments.get("username", "")),
                            password=str(tc.arguments.get("password", "")),
                            extra_fields=tc.arguments.get("extra_fields"),
                            submit_text=str(tc.arguments.get("submit_text", "")),
                        )
                    elif tc.name == "browser_smart_search":
                        result = self._browser.smart_search(
                            query=str(tc.arguments.get("query", "")),
                            url=str(tc.arguments.get("url", "")),
                            max_results=int(tc.arguments.get("max_results", 10)),
                            extract_cards=bool(tc.arguments.get("extract_cards", True)),
                        )
                    elif tc.name == "browser_smart_add_to_cart":
                        result = self._browser.smart_add_to_cart(
                            product_name=str(tc.arguments.get("product_name", "")),
                            confirmed=bool(tc.arguments.get("confirmed", False)),
                            quantity=tc.arguments.get("quantity"),
                        )
                    elif tc.name == "browser_allowed_domains":
                        result = self._browser.manage_allowed_domains(
                            add=str(tc.arguments.get("add", "")),
                            remove=str(tc.arguments.get("remove", "")),
                            list_domains=bool(tc.arguments.get("list", False)),
                        )
                    # --- Фаза 1: базовые примитивы (7) ---
                    elif tc.name == "browser_scroll":
                        result = self._browser.scroll(
                            amount=int(tc.arguments.get("amount", 300)),
                            direction=str(tc.arguments.get("direction", "down")),
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_hover":
                        result = self._browser.hover(
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_double_click":
                        result = self._browser.double_click(
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_right_click":
                        result = self._browser.right_click(
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_type_text":
                        result = self._browser.type_text(
                            selector=str(tc.arguments.get("selector", "")),
                            text=str(tc.arguments.get("text", "")),
                            delay=int(tc.arguments.get("delay", 50)),
                        )
                    elif tc.name == "browser_press_key":
                        result = self._browser.press_key(
                            key=str(tc.arguments.get("key", "")),
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_drag":
                        result = self._browser.drag(
                            source_selector=str(tc.arguments.get("source_selector", "")),
                            target_selector=str(tc.arguments.get("target_selector", "")),
                        )
                    # --- Фаза 2: мульти-табы (4) ---
                    elif tc.name == "browser_new_tab":
                        result = self._browser.new_tab(
                            url=str(tc.arguments.get("url", "")),
                        )
                    elif tc.name == "browser_switch_tab":
                        result = self._browser.switch_tab(
                            index=int(tc.arguments.get("index", 0)),
                        )
                    elif tc.name == "browser_close_tab":
                        result = self._browser.close_tab(
                            index=int(tc.arguments.get("index", -1)),
                        )
                    elif tc.name == "browser_list_tabs":
                        result = self._browser.list_tabs()
                    # --- Фаза 3: диалоги, загрузки, хранилище (4) ---
                    elif tc.name == "browser_handle_dialog":
                        result = self._browser.handle_dialog(
                            action=str(tc.arguments.get("action", "accept")),
                            prompt_text=str(tc.arguments.get("prompt_text", "")),
                        )
                    elif tc.name == "browser_upload_file":
                        result = self._browser.upload_file(
                            selector=str(tc.arguments.get("selector", "")),
                            file_path=str(tc.arguments.get("file_path", "")),
                        )
                    elif tc.name == "browser_cookies":
                        result = self._browser.cookies(
                            action=str(tc.arguments.get("action", "get")),
                            cookie_data=tc.arguments.get("cookie_data"),
                        )
                    elif tc.name == "browser_local_storage":
                        result = self._browser.local_storage(
                            action=str(tc.arguments.get("action", "get")),
                            key=str(tc.arguments.get("key", "")),
                            value=str(tc.arguments.get("value", "")),
                        )
                    # --- Фаза 4: визуальный режим (3) ---
                    elif tc.name == "browser_screenshot_element":
                        result = self._browser.screenshot_element(
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_element_som":
                        result = self._browser.element_som(
                            max_elements=int(tc.arguments.get("max_elements", 30)),
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_visual_qa":
                        result = self._browser.visual_qa(
                            question=str(tc.arguments.get("question", "")),
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    # --- Фаза 5: сеть и iframe (3) ---
                    elif tc.name == "browser_network_requests":
                        result = self._browser.network_requests(
                            action=str(tc.arguments.get("action", "list")),
                            url_filter=str(tc.arguments.get("url_filter", "")),
                        )
                    elif tc.name == "browser_iframe_switch":
                        result = self._browser.iframe_switch(
                            action=str(tc.arguments.get("action", "list")),
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_device_emulate":
                        result = self._browser.device_emulate(
                            device=str(tc.arguments.get("device", "Desktop")),
                        )
                    # --- Фаза 6: смарт-тулы v2 (4) ---
                    elif tc.name == "browser_smart_form":
                        result = self._browser.smart_form(
                            url=str(tc.arguments.get("url", "")),
                            fields=tc.arguments.get("fields", {}),
                        )
                    elif tc.name == "browser_smart_extract":
                        result = self._browser.smart_extract(
                            extract_type=str(tc.arguments.get("extract_type", "tables")),
                            selector=str(tc.arguments.get("selector", "")),
                        )
                    elif tc.name == "browser_smart_checkout":
                        result = self._browser.smart_checkout(
                            url=str(tc.arguments.get("url", "")),
                            steps=tc.arguments.get("steps"),
                            auto_continue=bool(tc.arguments.get("auto_continue", False)),
                        )
                    elif tc.name == "browser_smart_captcha_detect":
                        result = self._browser.smart_captcha_detect()
                    else:
                        result = {"error": f"Неизвестный browser-тул: {tc.name}"}
                except PlaywrightUnavailableError as exc:
                    result = {"error": f"Браузер недоступен: {exc}"}
                return json.dumps(result, ensure_ascii=True)

            else:
                return json.dumps({"error": f"Неизвестный инструмент: {tc.name}"})

        except Exception as exc:
            return json.dumps({"error": str(exc)})

    # ── Legacy: синхронный chat_stream (для совместимости) ──
    # Удалён — теперь chat_stream использует реальный стриминг

    async def chat_with_tools(
        self,
        payload: ChatRequest,
        tools: list[dict[str, object]],
    ) -> ToolStepChatResult:
        messages = list(payload.history)
        messages.append(ChatMessage(role="user", content=payload.message))

        candidate_models = self.model_router.candidate_models(
            payload.task_type,
            payload.model,
            message=payload.message,
            history=messages,
            repo_profile=payload.repo_profile,
            path_prefix=payload.retrieval_path_prefix,
            routing_policy=payload.routing_policy,
        )
        if payload.pin_model and payload.model:
            candidate_models = [payload.model]
        attempted: list[str] = []
        errors: list[str] = []

        for model_name in candidate_models:
            provider_name = self.model_router.provider_for_model(model_name)
            provider = self.providers.get(provider_name)
            attempted.append(model_name)
            if provider is None:
                errors.append(f"Provider '{provider_name}' missing for '{model_name}'.")
                continue
            generate_with_tools = getattr(provider, "generate_with_tools", None)
            if generate_with_tools is None:
                errors.append(f"Provider '{provider_name}' does not support native tools.")
                continue
            if self.circuit_breaker and not self.circuit_breaker.is_available(provider_name):
                errors.append(f"Provider '{provider_name}' circuit is open.")
                continue
            try:
                result: ProviderToolResponse = await generate_with_tools(
                    model_name=model_name,
                    messages=messages,
                    tools=tools,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                )
                if self.circuit_breaker:
                    self.circuit_breaker.record_success(provider_name)
                return ToolStepChatResult(
                    provider=provider_name,
                    model=model_name,
                    content=result.content,
                    tool_calls=list(result.tool_calls),
                    attempted_models=attempted,
                )
            except ProviderError as exc:
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(provider_name)
                errors.append(str(exc))

        raise ProviderError(" | ".join(errors) if errors else "No tool-capable models available.")

    async def fim_complete(self, payload: FimCompletionRequest) -> FimCompletionResponse:
        path_hint = f"File: {payload.path}\n" if payload.path else ""
        lang_hint = f"Language: {payload.language}\n" if payload.language else ""
        message = "\n".join(
            [
                "Complete the code at the cursor. Return ONLY the text to insert.",
                "No markdown, no explanation, no quotes.",
                "",
                path_hint + lang_hint,
                "Before cursor:",
                "```",
                payload.prefix[-2500:],
                "```",
                "",
                "After cursor:",
                "```",
                payload.suffix[:800],
                "```",
            ]
        ).strip()
        chat_payload = ChatRequest(
            message=message,
            task_type=payload.task_type,
            model=payload.model,
            use_memory=False,
            use_retrieval=False,
            temperature=payload.temperature,
            max_tokens=max(64, payload.max_tokens),
        )
        result = await self.chat(chat_payload)
        insert_text = result.response.strip()
        if not insert_text or "\n\n" in insert_text:
            insert_text = ""
        return FimCompletionResponse(
            insert_text=insert_text,
            provider=result.provider,
            model=result.model,
            attempted_models=result.attempted_models,
        )

    async def _apply_dual_pass(
        self,
        *,
        payload: ChatRequest,
        draft: str,
        draft_model: str,
    ) -> tuple[str, Optional[str]]:
        validator_prompt = (
            "Review the draft answer for quality and correctness.\n"
            f"User request:\n{payload.message}\n\n"
            f"Draft (model={draft_model}):\n{draft}\n\n"
            "If the draft is acceptable, respond with exactly: APPROVED\n"
            "Otherwise respond with an improved final answer only (no preamble)."
        )
        validator_models = self.model_router.candidate_models(
            TaskType.review,
            None,
            message=validator_prompt,
            repo_profile=payload.repo_profile,
            path_prefix=payload.retrieval_path_prefix,
            routing_policy=payload.routing_policy,
        )
        validator_messages = [
            ChatMessage(role="system", content="You are a strict code review validator."),
            ChatMessage(role="user", content=validator_prompt),
        ]
        for model_name in validator_models:
            provider_name = self.model_router.provider_for_model(model_name)
            provider = self.providers.get(provider_name)
            if provider is None:
                continue
            if self.circuit_breaker and not self.circuit_breaker.is_available(provider_name):
                continue
            try:
                validated = await self._generate_with_retries(
                    provider=provider,
                    model_name=model_name,
                    messages=validator_messages,
                    temperature=0.1,
                    max_tokens=min(payload.max_tokens, 2000),
                )
                if self.circuit_breaker:
                    self.circuit_breaker.record_success(provider_name)
                cleaned = validated.strip()
                if cleaned.upper().startswith("APPROVED"):
                    return draft, model_name
                if cleaned:
                    return cleaned, model_name
            except ProviderError:
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(provider_name)
                continue
        return draft, None

    def providers_info(self) -> list[ProviderInfo]:
        return [
            ProviderInfo(provider=provider_name, models=provider.list_models())
            for provider_name, provider in self.providers.items()
        ]

    def get_session_history(self, session_id: str) -> list[ChatMessage]:
        return self.memory_store.get(session_id)

    def clear_session(self, session_id: str) -> bool:
        return self.memory_store.clear(session_id)

    # ── FTS5 Search ──

    def search_session_messages(
        self, session_id: str, query: str, limit: int = 20
    ) -> list:
        """FTS5-поиск по сообщениям в сессии."""
        history = self.memory_store.get(session_id)
        results = []
        q = query.lower().strip()

        for msg in history:
            content_lower = msg.content.lower()
            idx = content_lower.find(q)
            if idx == -1:
                continue
            start = max(0, idx - 100)
            end = min(len(msg.content), idx + len(query) + 100)
            snippet = msg.content[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(msg.content):
                snippet = snippet + "..."

            results.append({
                "session_id": session_id,
                "role": msg.role,
                "content_snippet": snippet,
                "match_position": idx,
            })

            if len(results) >= limit:
                break

        return results

    def search_all_sessions(self, query: str, limit: int = 30) -> list:
        """Глобальный FTS5-поиск по всем сессиям."""
        results = []
        q = query.lower().strip()

        # Получаем все session_id из memory_store
        # SQLiteMemoryStore имеет метод list_session_ids()
        all_sessions = getattr(self.memory_store, "list_session_ids", None)
        if all_sessions is None:
            return results

        session_ids = all_sessions()
        for sid in session_ids:
            if len(results) >= limit:
                break
            matches = self.search_session_messages(sid, query, limit=limit - len(results))
            results.extend(matches)

        return results[:limit]

    def export_session_markdown(self, session_id: str) -> tuple[str, int]:
        history = self.memory_store.get(session_id)
        lines: list[str] = [f"# Session {session_id}", ""]
        for index, message in enumerate(history, start=1):
            role = message.role.capitalize()
            lines.append(f"## {index}. {role}")
            lines.append(message.content)
            lines.append("")
        content = "\n".join(lines).strip() + "\n"
        return content, len(history)

    def export_session_txt(self, session_id: str) -> tuple[str, int]:
        history = self.memory_store.get(session_id)
        lines: list[str] = [f"Session: {session_id}", ""]
        for message in history:
            lines.append(f"[{message.role}] {message.content}")
        content = "\n".join(lines).strip() + "\n"
        return content, len(history)

    def export_session_json(self, session_id: str) -> tuple[str, int]:
        history = self.memory_store.get(session_id)
        data = {
            "session_id": session_id,
            "messages": [{"role": message.role, "content": message.content} for message in history],
        }
        return json.dumps(data, ensure_ascii=True, indent=2) + "\n", len(history)

    async def providers_status(self) -> list[ProviderStatus]:
        statuses: list[ProviderStatus] = []
        for provider_name, provider in self.providers.items():
            ok, detail = await provider.check_health()
            statuses.append(ProviderStatus(provider=provider_name, ok=ok, detail=detail))
        return statuses

    def _build_cache_key(
        self,
        payload: ChatRequest,
        messages: list[ChatMessage],
        candidate_models: list[str],
    ) -> str:
        content = {
            "task_type": payload.task_type.value,
            "requested_model": payload.model,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
            "use_retrieval": payload.use_retrieval,
            "retrieval_limit": payload.retrieval_limit,
            "retrieval_path_prefix": payload.retrieval_path_prefix,
            "repo_profile": payload.repo_profile,
            "routing_policy": payload.routing_policy,
            "candidate_models": candidate_models,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
        }
        return json.dumps(content, ensure_ascii=True, sort_keys=True)

    def _get_cached(self, cache_key: str) -> Optional[ChatResponse]:
        if self.cache_ttl_seconds <= 0:
            return None
        if self.response_cache is None:
            return None
        cached_payload = self.response_cache.get(cache_key)
        if cached_payload is None:
            return None
        return ChatResponse.model_validate_json(cached_payload)

    def _set_cached(self, cache_key: str, response: ChatResponse) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        if self.response_cache is None:
            return
        self.response_cache.set(cache_key, response.model_dump_json(), self.cache_ttl_seconds)

    def _record_chat_telemetry(
        self,
        *,
        started_at: float,
        success: bool,
        cache_hit: bool,
        selected_model: str | None,
        response_text: str,
        fallback_used: bool,
    ) -> None:
        if self.telemetry is None:
            return
        latency_ms = int((time() - started_at) * 1000)
        # Simple proxy cost estimate for trend tracking, not billing-grade.
        estimated_cost_usd = len(response_text) * 0.000002
        self.telemetry.record_chat(
            success=success,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            selected_model=selected_model,
            estimated_cost_usd=estimated_cost_usd,
            response_text=response_text,
            fallback_used=fallback_used,
        )

    @staticmethod
    def _sse_event(event_name: str, payload: dict[str, object]) -> str:
        return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"

    async def _generate_with_retries(
        self,
        *,
        provider: BaseProvider,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        last_error: ProviderError | None = None
        for attempt in range(self._provider_retry_attempts):
            try:
                return await provider.generate(
                    model_name=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except ProviderError as exc:
                last_error = exc
                is_last_attempt = attempt >= (self._provider_retry_attempts - 1)
                if is_last_attempt:
                    break
                if self._provider_retry_backoff_ms > 0:
                    await asyncio.sleep((self._provider_retry_backoff_ms * (2**attempt)) / 1000.0)
        raise ProviderError(str(last_error) if last_error else "Provider request failed.")
