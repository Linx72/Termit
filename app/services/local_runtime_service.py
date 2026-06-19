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
    def __init__(
        self,
        ollama_base_url: str,
        openai_compat_base_url: str,
        required_ollama_models: list[str] | None = None,
        retrieval_mode: str = "keyword",
        *,
        runtime_primary_model: str = "",
        teacher_model: str = "",
        teacher_fallback_model: str = "",
        teacher_ollama_models: list[str] | None = None,
    ) -> None:
        self._ollama_base_url = ollama_base_url.rstrip("/")
        self._openai_compat_base_url = openai_compat_base_url.rstrip("/")
        self._required_ollama_models = list(required_ollama_models or [])
        self._retrieval_mode = retrieval_mode.strip().lower() or "keyword"
        self._runtime_primary_model = runtime_primary_model.strip()
        self._teacher_model = teacher_model.strip()
        self._teacher_fallback_model = teacher_fallback_model.strip()
        self._teacher_ollama_models = list(teacher_ollama_models or [])

    @staticmethod
    def collect_required_ollama_models(
        *,
        default_model: str,
        code_model: str,
        analysis_model: str,
        retrieval_embed_model: str,
        fast_model: str = "",
        code_fallback_model: str = "",
    ) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for raw in (
            default_model,
            code_model,
            analysis_model,
            retrieval_embed_model,
            fast_model,
            code_fallback_model,
        ):
            candidate = raw.strip()
            if not candidate:
                continue
            if candidate.startswith("ollama:"):
                bare = candidate.split(":", 1)[1].strip()
            elif ":" in candidate:
                continue
            else:
                bare = candidate
            if bare and bare not in seen:
                seen.add(bare)
                names.append(bare)
        return names

    async def check_required_models(self) -> tuple[list[str], list[str]]:
        required = list(self._required_ollama_models)
        if not required:
            return required, []
        try:
            listed = await self.list_local_models()
        except LocalRuntimeError:
            return required, list(required)
        installed = {item.model.split(":", 1)[-1] for item in listed.models}
        missing: list[str] = []
        for name in required:
            if any(
                inst == name or inst.startswith(f"{name}:") or name.startswith(f"{inst}:")
                for inst in installed
            ):
                continue
            missing.append(name)
        return required, missing

    async def status(self) -> LocalRuntimeStatusResponse:
        ollama_ok, ollama_detail = await self._probe(f"{self._ollama_base_url}/api/tags")
        openai_compat_ok, openai_compat_detail = await self._probe(f"{self._openai_compat_base_url}/v1/models")
        required, missing = await self.check_required_models()
        if missing and ollama_ok:
            ollama_detail = (
                f"{ollama_detail}; missing models: {', '.join(missing)} "
                f"(run: ollama pull {' && ollama pull '.join(missing)})"
            )
            ollama_ok = False
        return LocalRuntimeStatusResponse(
            providers=[
                ProviderStatus(provider="ollama", ok=ollama_ok, detail=ollama_detail),
                ProviderStatus(
                    provider="openai_compat",
                    ok=openai_compat_ok,
                    detail=openai_compat_detail,
                ),
            ],
            required_ollama_models=required,
            missing_ollama_models=missing,
            retrieval_mode=self._retrieval_mode,
            runtime_primary_model=self._runtime_primary_model,
            teacher_model=self._teacher_model,
            teacher_fallback_model=self._teacher_fallback_model,
            teacher_ollama_models=list(self._teacher_ollama_models),
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

    async def warm_ollama_models(
        self,
        models: list[str] | None = None,
        *,
        max_models: int = 3,
    ) -> dict[str, object]:
        """Минимальный chat ping — загрузка весов в VRAM/RAM (снижает cold-start TTFT)."""
        targets: list[str] = []
        if models:
            for raw in models:
                name = raw.strip()
                if name.startswith("ollama:"):
                    name = name.split(":", 1)[1]
                if name:
                    targets.append(name)
        else:
            targets = list(self._required_ollama_models[:max(1, max_models)])
        results: list[dict[str, object]] = []
        for bare in targets:
            payload = {
                "model": bare,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "options": {"num_predict": 1, "temperature": 0.0},
            }
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    response = await client.post(f"{self._ollama_base_url}/api/chat", json=payload)
                ok = response.status_code < 400
                results.append(
                    {
                        "model": f"ollama:{bare}",
                        "ok": ok,
                        "status_code": response.status_code,
                    }
                )
            except httpx.HTTPError as exc:
                results.append({"model": f"ollama:{bare}", "ok": False, "error": str(exc)})
        warmed = sum(1 for item in results if item.get("ok"))
        return {"warmed": warmed, "total": len(results), "results": results}

    async def _probe(self, url: str) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
            if response.status_code >= 400:
                return False, f"HTTP {response.status_code}"
            return True, "reachable"
        except httpx.HTTPError as exc:
            return False, str(exc)
