import json
from collections.abc import AsyncIterator

import httpx

from app.domain.schemas import ChatMessage
from app.services.providers.base import (
    BaseProvider,
    ProviderError,
    ProviderStreamChunk,
    ProviderToolCall,
    ProviderToolResponse,
)


class OllamaProvider(BaseProvider):
    """Ollama-провайдер с нативным NDJSON-стримингом и tool calling."""

    name = "ollama"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _strip_prefix(self, model_name: str) -> str:
        if model_name.startswith("ollama:"):
            return model_name.split(":", 1)[1]
        return model_name

    async def generate(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = {
            "model": self._strip_prefix(model_name),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Ollama request failed for {self.base_url}: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise ProviderError(f"Ollama error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()

    async def generate_stream(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[ProviderStreamChunk]:
        """
        Настоящий NDJSON-стриминг через Ollama /api/chat stream=true.
        
        Ollama отдаёт по одному JSON-объекту на строку (NDJSON).
        Каждый объект содержит message.content с инкрементальным токеном.
        """
        payload: dict[str, object] = {
            "model": self._strip_prefix(model_name),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools

        # Агрегатор tool_calls (Ollama может отдавать tool_calls в финальном объекте done=true)
        sent_tool_calls: set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderError(
                            f"Ollama stream error {response.status_code}: {body.decode()}"
                        )

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        message = event.get("message") or {}
                        content = str(message.get("content") or "")

                        # Текстовый токен
                        if content:
                            yield ProviderStreamChunk(token=content)

                        # Tool calls (Ollama отправляет их в финальном объекте)
                        tool_calls_raw = message.get("tool_calls") or []
                        if isinstance(tool_calls_raw, list):
                            for tc in tool_calls_raw:
                                if not isinstance(tc, dict):
                                    continue
                                func = tc.get("function") or {}
                                name = str(func.get("name") or "")
                                if not name:
                                    continue
                                tc_id = f"{name}_{tc.get('id', '')}"
                                if tc_id in sent_tool_calls:
                                    continue
                                sent_tool_calls.add(tc_id)

                                raw_args = func.get("arguments") or {}
                                if isinstance(raw_args, str):
                                    try:
                                        arguments = json.loads(raw_args)
                                    except json.JSONDecodeError:
                                        arguments = {}
                                elif isinstance(raw_args, dict):
                                    arguments = raw_args
                                else:
                                    arguments = {}

                                yield ProviderStreamChunk(
                                    tool_call_delta=ProviderToolCall(
                                        id=str(tc.get("id") or name),
                                        name=name,
                                        arguments=arguments,
                                    )
                                )

                        # Поток завершён
                        if event.get("done") is True:
                            yield ProviderStreamChunk(is_done=True)

        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Ollama stream failed for {self.base_url}: {exc}"
            ) from exc

    def _parse_tool_calls(self, message: dict[str, object]) -> list[ProviderToolCall]:
        tool_calls_raw = message.get("tool_calls") or []
        if not isinstance(tool_calls_raw, list):
            return []
        parsed: list[ProviderToolCall] = []
        for item in tool_calls_raw:
            if not isinstance(item, dict):
                continue
            function = item.get("function") or {}
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "")
            if not name:
                continue
            raw_args = function.get("arguments") or {}
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    arguments = {}
            elif isinstance(raw_args, dict):
                arguments = raw_args
            else:
                arguments = {}
            parsed.append(
                ProviderToolCall(
                    id=str(item.get("id") or name),
                    name=name,
                    arguments=arguments,
                )
            )
        return parsed

    async def generate_with_tools(
        self,
        model_name: str,
        messages: list[ChatMessage],
        tools: list[dict[str, object]],
        temperature: float,
        max_tokens: int,
    ) -> ProviderToolResponse:
        payload = {
            "model": self._strip_prefix(model_name),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "tools": tools,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Ollama request failed for {self.base_url}: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise ProviderError(f"Ollama error {resp.status_code}: {resp.text}")
        data = resp.json()
        message = data.get("message", {})
        if not isinstance(message, dict):
            message = {}
        return ProviderToolResponse(
            content=str(message.get("content") or "").strip(),
            tool_calls=self._parse_tool_calls(message),
        )

    def list_models(self) -> list[str]:
        return ["ollama:termit-core-ft", "ollama:qwen2.5-coder", "ollama:codellama"]

    async def check_health(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
            if resp.status_code >= 400:
                return False, f"HTTP {resp.status_code}"
            return True, "reachable"
        except httpx.HTTPError as exc:
            return False, str(exc)
