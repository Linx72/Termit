import httpx

from app.domain.schemas import ChatMessage
from app.services.providers.base import BaseProvider, ProviderError


class OpenAICompatProvider(BaseProvider):
    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _strip_prefix(self, model_name: str) -> str:
        if model_name.startswith("openai_compat:"):
            return model_name.split(":", 1)[1]
        return model_name

    async def generate(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self._strip_prefix(model_name),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
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
            return ""
        return choices[0].get("message", {}).get("content", "").strip()

    def list_models(self) -> list[str]:
        return [
            "openai_compat:deepseek-ai/deepseek-coder-33b-instruct",
            "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
        ]

    async def check_health(self) -> tuple[bool, str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models", headers=headers)
            if resp.status_code in {401, 403}:
                return True, f"reachable (auth required, HTTP {resp.status_code})"
            if resp.status_code >= 400:
                return False, f"HTTP {resp.status_code}"
            return True, "reachable"
        except httpx.HTTPError as exc:
            return False, str(exc)
