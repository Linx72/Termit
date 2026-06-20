import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent_loop_service import _model_supports_native_tool_calls
from app.domain.schemas import ChatMessage
from app.services.providers.ollama_provider import OllamaProvider


class OllamaProviderTests(unittest.TestCase):
    def test_generate_with_tools_parses_tool_calls(self) -> None:
        provider = OllamaProvider("http://127.0.0.1:11434")
        response_body = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": {"path": "app", "file": "main.py"},
                        }
                    }
                ],
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_body

        with patch("httpx.AsyncClient") as client_cls:
            client = AsyncMock()
            client_cls.return_value.__aenter__.return_value = client
            client.post = AsyncMock(return_value=mock_resp)

            import asyncio

            result = asyncio.run(
                provider.generate_with_tools(
                    "ollama:qwen2.5-coder",
                    [ChatMessage(role="user", content="read main")],
                    tools=[{"type": "function", "function": {"name": "read_file"}}],
                    temperature=0.2,
                    max_tokens=256,
                )
            )

        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].name, "read_file")
        self.assertEqual(result.tool_calls[0].arguments.get("file"), "main.py")
        call_kwargs = client.post.await_args.kwargs
        self.assertIn("tools", call_kwargs.get("json", {}))

    def test_model_supports_native_tool_calls(self) -> None:
        self.assertTrue(_model_supports_native_tool_calls("ollama:qwen2.5-coder"))
        self.assertTrue(_model_supports_native_tool_calls("openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct"))
        self.assertFalse(_model_supports_native_tool_calls("local:foo"))


if __name__ == "__main__":
    unittest.main()
