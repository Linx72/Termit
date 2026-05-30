from __future__ import annotations

import httpx

from app.domain.schemas import (
    LocalModelInfo,
    LocalModelPullResponse,
    LocalModelsResponse,
    LocalRuntimeStatusResponse,
    ProviderStatus,
)


class LocalRuntimeError(Exception):
    pass


class LocalRuntimeService:
    def __init__(self, ollama_base_url: str, openai_compat_base_url: str) -> None:
        self._ollama_base_url = ollama_base_url.rstrip("/")
        self._openai_compat_base_url = openai_compat_base_url.rstrip("/")

    async def status(self) -> LocalRuntimeStatusResponse:
        ollama_ok, ollama_detail = await self._probe(f"{self._ollama_base_url}/api/tags")
        openai_compat_ok, openai_compat_detail = await self._probe(f"{self._openai_compat_base_url}/v1/models")
        return LocalRuntimeStatusResponse(
            providers=[
                ProviderStatus(provider="ollama", ok=ollama_ok, detail=ollama_detail),
                ProviderStatus(
                    provider="openai_compat",
                    ok=openai_compat_ok,
                    detail=openai_compat_detail,
                ),
            ]
        )

    async def list_local_models(self) -> LocalModelsResponse:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._ollama_base_url}/api/tags")
        except httpx.HTTPError as exc:
            raise LocalRuntimeError(f"Failed to reach Ollama runtime: {exc}") from exc

        if response.status_code >= 400:
            raise LocalRuntimeError(
                f"Ollama list models failed with HTTP {response.status_code}: {response.text}"
            )

        payload = response.json()
        models = payload.get("models", [])
        result: list[LocalModelInfo] = []
        for item in models:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            result.append(
                LocalModelInfo(
                    provider="ollama",
                    model=f"ollama:{name}",
                    size_bytes=item.get("size"),
                    modified_at=item.get("modified_at"),
                )
            )

        return LocalModelsResponse(runtime="local", models=result)

    async def pull_ollama_model(self, model: str) -> LocalModelPullResponse:
        clean_model = model.strip()
        if clean_model.startswith("ollama:"):
            clean_model = clean_model.split(":", 1)[1]
        if not clean_model:
            raise LocalRuntimeError("Model name must not be empty.")

        payload = {"name": clean_model, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(f"{self._ollama_base_url}/api/pull", json=payload)
        except httpx.HTTPError as exc:
            raise LocalRuntimeError(f"Ollama pull request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LocalRuntimeError(
                f"Ollama pull failed with HTTP {response.status_code}: {response.text}"
            )

        body = response.json()
        status = str(body.get("status", "accepted"))
        detail = str(body.get("detail", ""))
        return LocalModelPullResponse(
            accepted=True,
            provider="ollama",
            model=f"ollama:{clean_model}",
            status=status,
            detail=detail,
        )

    async def _probe(self, url: str) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
            if response.status_code >= 400:
                return False, f"HTTP {response.status_code}"
            return True, "reachable"
        except httpx.HTTPError as exc:
            return False, str(exc)
