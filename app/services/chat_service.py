import uuid
import json
from typing import AsyncIterator

from app.domain.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ProviderInfo,
    ProviderStatus,
)
from app.services.memory_store import MemoryBackend
from app.services.model_router import ModelRouter
from app.services.providers.base import BaseProvider, ProviderError


class ChatService:
    def __init__(
        self,
        model_router: ModelRouter,
        providers: dict[str, BaseProvider],
        memory_store: MemoryBackend,
    ) -> None:
        self.model_router = model_router
        self.providers = providers
        self.memory_store = memory_store

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        candidate_models = self.model_router.candidate_models(payload.task_type, payload.model)

        session_id = payload.session_id
        if payload.use_memory and not session_id:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        messages = list(payload.history)
        if payload.use_memory and session_id:
            messages.extend(self.memory_store.get(session_id))
        messages.append(ChatMessage(role="user", content=payload.message))

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

            try:
                response_text = await provider.generate(
                    model_name=model_name,
                    messages=messages,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                )
                selected_model = model_name
                selected_provider = provider_name
                break
            except ProviderError as exc:
                errors.append(str(exc))

        if not selected_model:
            raise ProviderError(" | ".join(errors) if errors else "No available models.")

        if payload.use_memory and session_id:
            self.memory_store.append(session_id, ChatMessage(role="user", content=payload.message))
            self.memory_store.append(session_id, ChatMessage(role="assistant", content=response_text))

        return ChatResponse(
            provider=selected_provider,
            model=selected_model,
            task_type=payload.task_type,
            session_id=session_id,
            history_size=len(messages) + 1,
            attempted_models=attempted_models,
            response=response_text,
        )

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
        header = (
            f'event: meta\ndata: {{"provider":"{response.provider}",'
            f'"model":"{response.model}","session_id":"{response.session_id or ""}",'
            f'"history_size":{response.history_size},"attempted_models":"'
            f'{" -> ".join(response.attempted_models)}"}}\n\n'
        )
        yield header

        text = response.response or ""
        chunk_size = 80
        for index in range(0, len(text), chunk_size):
            chunk = text[index : index + chunk_size]
            safe_chunk = chunk.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            yield f'event: token\ndata: {{"text":"{safe_chunk}"}}\n\n'

        yield "event: done\ndata: {}\n\n"
