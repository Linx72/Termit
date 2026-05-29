import httpx

from app.domain.schemas import ChatMessage
from app.services.providers.base import BaseProvider, ProviderError


class OllamaProvider(BaseProvider):
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

    def list_models(self) -> list[str]:
        return ["ollama:deepseek-coder", "ollama:qwen2.5-coder", "ollama:codellama"]

    async def check_health(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
            if resp.status_code >= 400:
                return False, f"HTTP {resp.status_code}"
            return True, "reachable"
        except httpx.HTTPError as exc:
            return False, str(exc)
