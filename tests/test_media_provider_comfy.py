"""Тесты ComfyUI SDXL provider и wiring в Media Studio."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.media_asset_store import MediaAssetStore
from app.services.media_generation_service import MediaGenerationService, MediaStudioError
from app.services.media_provider_comfy import (
    ComfyImageProvider,
    build_sdxl_workflow,
    load_workflow_template,
    _round_sdxl_dim,
)
from app.services.agent_tool_schema import TOOL_DEFINITIONS

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "data/media/workflows/sdxl_t2i_api.json"


class ComfyWorkflowTests(unittest.TestCase):
    def test_round_sdxl_dim_multiple_of_8(self) -> None:
        self.assertEqual(_round_sdxl_dim(513), 512)
        self.assertEqual(_round_sdxl_dim(1024), 1024)
        self.assertEqual(_round_sdxl_dim(993), 992)

    def test_build_workflow_patches_prompt_and_size(self) -> None:
        template = load_workflow_template(WORKFLOW)
        workflow = build_sdxl_workflow(
            template,
            prompt="Termit logo dark blue",
            width=512,
            height=768,
            checkpoint="sd_xl_base_1.0.safetensors",
            seed=42,
        )
        self.assertEqual(workflow["6"]["inputs"]["text"], "Termit logo dark blue")
        self.assertEqual(workflow["5"]["inputs"]["width"], 512)
        self.assertEqual(workflow["5"]["inputs"]["height"], 768)
        self.assertEqual(workflow["3"]["inputs"]["seed"], 42)


class ComfyImageProviderTests(unittest.TestCase):
    def test_generate_downloads_png_from_history(self) -> None:
        provider = ComfyImageProvider(
            base_url="http://127.0.0.1:8188",
            workflow_path=str(WORKFLOW),
            timeout_sec=30.0,
        )
        fake_png = b"\x89PNG\r\n\x1a\n"

        mock_client = MagicMock()
        prompt_response = MagicMock()
        prompt_response.status_code = 200
        prompt_response.json.return_value = {"prompt_id": "pid-1"}

        history_pending = MagicMock()
        history_pending.status_code = 200
        history_pending.json.return_value = {}

        history_done = MagicMock()
        history_done.status_code = 200
        history_done.json.return_value = {
            "pid-1": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "termit_00001.png", "subfolder": "", "type": "output"}
                        ]
                    }
                }
            }
        }

        view_response = MagicMock()
        view_response.status_code = 200
        view_response.content = fake_png

        mock_client.post.return_value = prompt_response
        mock_client.get.side_effect = [history_pending, history_done, view_response]

        with patch("app.services.media_provider_comfy.httpx.Client") as client_cls:
            client_cls.return_value.__enter__.return_value = mock_client
            result = provider.generate(prompt="hero banner", width=1024, height=1024)

        self.assertEqual(result.bytes_data, fake_png)
        self.assertEqual(result.provider, "comfy")
        self.assertEqual(result.model, "sd_xl_base_1.0.safetensors")

    def test_health_check_false_on_connection_error(self) -> None:
        provider = ComfyImageProvider(base_url="http://127.0.0.1:59999")
        with patch("app.services.media_provider_comfy.httpx.Client") as client_cls:
            client_cls.return_value.__enter__.side_effect = OSError("refused")
            self.assertFalse(provider.health_check())


class MediaComfyIntegrationTests(unittest.TestCase):
    def test_comfy_unavailable_raises(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        try:
            store = MediaAssetStore(tmp.name)
            service = MediaGenerationService(
                asset_store=store,
                enabled=True,
                image_provider_name="comfy",
                openai_api_key="",
                comfy_url="http://127.0.0.1:59999",
                comfy_workflow=str(WORKFLOW),
            )
            with self.assertRaises(MediaStudioError) as ctx:
                service.generate_image(prompt="test icon", width=512, height=512, provider="comfy")
            self.assertIn("ComfyUI недоступен", str(ctx.exception))
        finally:
            tmp.cleanup()

    def test_sdxl_alias_routes_to_comfy(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        try:
            store = MediaAssetStore(tmp.name)
            service = MediaGenerationService(
                asset_store=store,
                enabled=True,
                openai_api_key="",
                comfy_url="http://127.0.0.1:59999",
                comfy_workflow=str(WORKFLOW),
            )
            with patch.object(service._comfy, "health_check", return_value=True):
                with patch.object(
                    service._comfy,
                    "generate",
                    return_value=type(
                        "R",
                        (),
                        {
                            "bytes_data": b"\x89PNG",
                            "provider": "comfy",
                            "cost_usd": 0.0,
                            "revised_prompt": None,
                        },
                    )(),
                ):
                    result = service.generate_image(
                        prompt="alias test",
                        width=512,
                        height=512,
                        provider="sdxl",
                    )
            self.assertEqual(result.asset.provider, "comfy")
        finally:
            tmp.cleanup()

    def test_tool_schema_lists_comfy_provider(self) -> None:
        props = TOOL_DEFINITIONS["generate_image"]["function"]["parameters"]["properties"]
        desc = props["provider"]["description"]
        self.assertIn("comfy", desc)
        self.assertIn("sdxl", desc)


if __name__ == "__main__":
    unittest.main()
