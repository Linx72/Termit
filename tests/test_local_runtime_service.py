import asyncio
import unittest
from unittest.mock import patch

from app.services.local_runtime_service import LocalRuntimeService


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object], text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses: dict[tuple[str, str], _FakeResponse], **kwargs) -> None:  # type: ignore[no-untyped-def]
        self._responses = responses

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    async def get(self, url: str):  # type: ignore[no-untyped-def]
        return self._responses[("GET", url)]

    async def post(self, url: str, json: dict[str, object]):  # type: ignore[no-untyped-def]
        self.last_post_payload = json
        return self._responses[("POST", url)]


class LocalRuntimeServiceTests(unittest.TestCase):
    def test_list_local_models_parses_ollama_tags(self) -> None:
        responses = {
            (
                "GET",
                "http://localhost:11434/api/tags",
            ): _FakeResponse(
                200,
                {
                    "models": [
                        {
                            "name": "qwen2.5-coder:14b",
                            "size": 123,
                            "modified_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )
        }
        service = LocalRuntimeService("http://localhost:11434", "http://localhost:8001")

        with patch(
            "app.services.local_runtime_service.httpx.AsyncClient",
            lambda **kwargs: _FakeAsyncClient(responses, **kwargs),
        ):
            result = asyncio.run(service.list_local_models())

        self.assertEqual(result.runtime, "local")
        self.assertEqual(len(result.models), 1)
        self.assertEqual(result.models[0].model, "ollama:qwen2.5-coder:14b")

    def test_pull_model_accepts_prefixed_name(self) -> None:
        responses = {
            (
                "POST",
                "http://localhost:11434/api/pull",
            ): _FakeResponse(200, {"status": "success", "detail": "downloaded"})
        }
        service = LocalRuntimeService("http://localhost:11434", "http://localhost:8001")
        fake_client = _FakeAsyncClient(responses)

        with patch(
            "app.services.local_runtime_service.httpx.AsyncClient",
            lambda **kwargs: fake_client,
        ):
            result = asyncio.run(service.pull_ollama_model("ollama:qwen2.5-coder:14b"))

        self.assertTrue(result.accepted)
        self.assertEqual(result.model, "ollama:qwen2.5-coder:14b")
        self.assertEqual(fake_client.last_post_payload["name"], "qwen2.5-coder:14b")

    def test_collect_required_ollama_models_deduplicates(self) -> None:
        names = LocalRuntimeService.collect_required_ollama_models(
            default_model="ollama:termit-core-ft",
            code_model="ollama:termit-core-ft",
            analysis_model="ollama:qwen2.5-coder",
            retrieval_embed_model="nomic-embed-text",
        )
        self.assertEqual(names, ["termit-core-ft", "qwen2.5-coder", "nomic-embed-text"])

    def test_check_required_models_reports_missing(self) -> None:
        responses = {
            ("GET", "http://localhost:11434/api/tags"): _FakeResponse(
                200,
                {"models": [{"name": "deepseek-coder:latest"}]},
            )
        }
        service = LocalRuntimeService(
            "http://localhost:11434",
            "http://localhost:8001",
            required_ollama_models=["deepseek-coder", "nomic-embed-text"],
        )
        with patch(
            "app.services.local_runtime_service.httpx.AsyncClient",
            lambda **kwargs: _FakeAsyncClient(responses, **kwargs),
        ):
            required, missing = asyncio.run(service.check_required_models())
        self.assertEqual(required, ["deepseek-coder", "nomic-embed-text"])
        self.assertEqual(missing, ["nomic-embed-text"])


if __name__ == "__main__":
    unittest.main()
