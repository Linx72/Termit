from __future__ import annotations

import json
import uuid
import asyncio
from time import time
from typing import AsyncIterator, Optional

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
from app.services.memory_store import MemoryBackend
from app.services.model_router import ModelRouter
from app.services.provider_circuit_breaker import ProviderCircuitBreaker
from app.services.providers.base import BaseProvider, ProviderError
from app.services.response_cache_store import ResponseCacheStore
from app.services.telemetry_store import TelemetryStore


class ChatService:
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
        retrieval_enabled: bool = True,
        provider_retry_attempts: int = 2,
        provider_retry_backoff_ms: int = 150,
        dual_pass_enabled: bool = False,
        dual_pass_task_types: str = "coding,review,debug",
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
        self._retrieval_enabled = retrieval_enabled
        self._provider_retry_attempts = max(1, provider_retry_attempts)
        self._provider_retry_backoff_ms = max(0, provider_retry_backoff_ms)
        self._dual_pass_enabled = dual_pass_enabled
        self._dual_pass_task_types = {
            item.strip().lower()
            for item in dual_pass_task_types.split(",")
            if item.strip()
        }

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        started_at = time()
        session_id = payload.session_id
        if payload.use_memory and not session_id:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        messages = list(payload.history)
        if payload.use_memory and session_id:
            messages.extend(self.memory_store.get(session_id))
        messages.append(ChatMessage(role="user", content=payload.message))

        compaction = self._compactor.compact(messages)
        messages = list(compaction.messages)
        retrieval_hits = 0
        if payload.use_retrieval and self._retrieval_enabled and self._retrieval is not None:
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
        if self._dual_pass_enabled and payload.task_type.value in self._dual_pass_task_types:
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

    async def chat_stream(self, payload: ChatRequest) -> AsyncIterator[str]:
        response = await self.chat(payload)
        yield self._sse_event(
            "meta",
            {
                "provider": response.provider,
                "model": response.model,
                "session_id": response.session_id or "",
                "history_size": response.history_size,
                "attempted_models": response.attempted_models,
                "context_compacted": response.context_compacted,
                "dropped_messages": response.dropped_messages,
                "retrieval_hits": response.retrieval_hits,
            },
        )

        text = response.response or ""
        chunk_size = 80
        for index in range(0, len(text), chunk_size):
            chunk = text[index : index + chunk_size]
            yield self._sse_event("token", {"text": chunk})

        yield self._sse_event("done", {})

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
