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


class OpenAICompatProvider(BaseProvider):
    """OpenAI-совместимый провайдер с нативным SSE-стримингом и tool calling."""

    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        # If the base URL already ends with /v1, don't prepend /v1 later
        self._api_url = self.base_url.removesuffix("/v1")

    def _strip_prefix(self, model_name: str) -> str:
        if model_name.startswith("openai_compat:"):
            return model_name.split(":", 1)[1]
        return model_name

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

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
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._api_url}/v1/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"OpenAI-compatible request failed for {self.base_url}: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise ProviderError(
                f"OpenAI-compatible endpoint error {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "").strip()

    async def generate_stream(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[ProviderStreamChunk]:
        """
        Настоящий SSE-стриминг через OpenAI /v1/chat/completions stream=true.
        
        Парсит SSE-события, агрегирует tool_call дельты (фрагменты аргументов),
        отдаёт reasoning-токены (для DeepSeek R1), текстовые токены,
        и финальный чанк с finish_reason + tool_calls.
        """
        payload: dict[str, object] = {
            "model": self._strip_prefix(model_name),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": False},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Агрегаторы для tool_call дельт (OpenAI шлёт аргументы фрагментами)
        tool_deltas: dict[int, dict[str, object]] = {}  # index → {id, name, arguments}

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{self._api_url}/v1/chat/completions",
                    json=payload,
                    headers=self._headers(),
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderError(
                            f"OpenAI-compatible stream error {response.status_code}: {body.decode()}"
                        )

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]  # убрать "data: "
                        if data_str.strip() == "[DONE]":
                            # Отдаём все накопленные tool_calls
                            for idx in sorted(tool_deltas.keys()):
                                td = tool_deltas[idx]
                                name = str(td.get("name") or "")
                                raw_args = td.get("arguments", "")
                                if isinstance(raw_args, str):
                                    try:
                                        args = json.loads(raw_args)
                                    except json.JSONDecodeError:
                                        args = {}
                                elif isinstance(raw_args, dict):
                                    args = raw_args
                                else:
                                    args = {}
                                yield ProviderStreamChunk(
                                    tool_call_delta=ProviderToolCall(
                                        id=str(td.get("id") or name),
                                        name=name,
                                        arguments=args,
                                    )
                                )
                            yield ProviderStreamChunk(is_done=True, finish_reason="stop")
                            break

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = event.get("choices", [])
                        if not choices:
                            continue

                        choice = choices[0]
                        delta = choice.get("delta", {})
                        finish = choice.get("finish_reason") or ""

                        # Reasoning-токен (DeepSeek R1 / Qwen3 thinking)
                        reasoning_content = delta.get("reasoning_content") or ""
                        if reasoning_content:
                            yield ProviderStreamChunk(reasoning=str(reasoning_content))
                            continue

                        # Tool call дельты (агрегируем)
                        tc_deltas = delta.get("tool_calls") or []
                        for tc in tc_deltas:
                            idx = int(tc.get("index", 0))
                            if idx not in tool_deltas:
                                tool_deltas[idx] = {
                                    "id": tc.get("id") or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            td = tool_deltas[idx]
                            if tc.get("id"):
                                td["id"] = tc["id"]
                            if tc.get("function", {}).get("name"):
                                td["name"] = tc["function"]["name"]
                            if tc.get("function", {}).get("arguments"):
                                td["arguments"] = td.get("arguments", "") + tc["function"]["arguments"]

                            # Отдаём имя инструмента как токен (для UI-индикатора)
                            if tc.get("function", {}).get("name"):
                                yield ProviderStreamChunk(
                                    tool_call_delta=ProviderToolCall(
                                        id=str(td.get("id") or ""),
                                        name=str(tc["function"]["name"]),
                                        arguments={},
                                    )
                                )

                        # Текстовый токен
                        content = delta.get("content") or ""
                        if content:
                            yield ProviderStreamChunk(token=str(content))

                        if finish:
                            # Отдаём накопленные tool_calls
                            for idx in sorted(tool_deltas.keys()):
                                td = tool_deltas[idx]
                                name = str(td.get("name") or "")
                                raw_args = td.get("arguments", "")
                                if isinstance(raw_args, str) and raw_args:
                                    try:
                                        args = json.loads(raw_args)
                                    except json.JSONDecodeError:
                                        args = {}
                                elif isinstance(raw_args, dict):
                                    args = raw_args
                                else:
                                    args = {}
                                if name:
                                    yield ProviderStreamChunk(
                                        tool_call_delta=ProviderToolCall(
                                            id=str(td.get("id") or name),
                                            name=name,
                                            arguments=args,
                                        )
                                    )
                            yield ProviderStreamChunk(
                                is_done=True,
                                finish_reason=str(finish),
                            )

        except httpx.HTTPError as exc:
            raise ProviderError(
                f"OpenAI-compatible stream failed for {self.base_url}: {exc}"
            ) from exc

    async def generate_with_tools(
        self,
        model_name: str,
        messages: list[ChatMessage],
        tools: list[dict[str, object]],
        temperature: float,
        max_tokens: int,
    ) -> ProviderToolResponse:
        headers = self._headers()
        payload = {
            "model": self._strip_prefix(model_name),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "tool_choice": "auto",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._api_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"OpenAI-compatible request failed for {self.base_url}: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise ProviderError(
                f"OpenAI-compatible endpoint error {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return ProviderToolResponse()
        message = choices[0].get("message", {})
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ProviderToolCall] = []
        for item in tool_calls_raw:
            function = item.get("function") or {}
            raw_args = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                ProviderToolCall(
                    id=str(item.get("id") or function.get("name") or "tool"),
                    name=str(function.get("name") or ""),
                    arguments=arguments,
                )
            )
        return ProviderToolResponse(
            content=str(message.get("content") or "").strip(),
            tool_calls=tool_calls,
            finish_reason=str(choices[0].get("finish_reason") or ""),
        )

    def list_models(self) -> list[str]:
        return [
            "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
            "openai_compat:deepseek-v4-pro",
            "openai_compat:deepseek-reasoner",
            "openai_compat:deepseek-chat",
        ]

    async def check_health(self) -> tuple[bool, str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._api_url}/v1/models", headers=headers)
            if resp.status_code in {401, 403}:
                return True, f"reachable (auth required, HTTP {resp.status_code})"
            if resp.status_code >= 400:
                return False, f"HTTP {resp.status_code}"
            return True, "reachable"
        except httpx.HTTPError as exc:
            return False, str(exc)
