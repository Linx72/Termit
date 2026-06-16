"""Media Studio Phase 1 — asset store, generation, API."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.media_asset_store import MediaAssetStore
from app.services.media_cost_service import estimate_storyboard_path
from app.services.media_generation_service import (
    MediaConfirmationRequired,
    MediaGenerationService,
    MediaStudioError,
)
from app.services.agent_tool_schema import TOOL_DEFINITIONS, build_openai_tools


ROOT = Path(__file__).resolve().parents[1]
STORYBOARD_EXAMPLE = ROOT / "data/media/examples/storyboard.example.json"


class MediaGenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = MediaAssetStore(self._tmp.name)
        self.service = MediaGenerationService(
            asset_store=self.store,
            enabled=True,
            confirm_cost_usd=0.5,
            image_provider_name="stub",
            openai_api_key="",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_generate_image_stub(self) -> None:
        result = self.service.generate_image(
            prompt="Termit app icon minimal blue",
            width=512,
            height=512,
            project_id="test-proj",
            scene_id="s01",
            provider="stub",
        )
        self.assertEqual(result.asset.mime, "image/png")
        self.assertEqual(result.asset.width, 512)
        self.assertEqual(result.asset.height, 512)
        path = self.store.resolve_path(result.asset)
        self.assertTrue(path.is_file())

    def test_generate_image_records_trace_span(self) -> None:
        from app.services.trace_span_store import TraceSpanStore

        with tempfile.TemporaryDirectory() as tmp:
            span_store = TraceSpanStore(str(Path(tmp) / "spans.db"))
            svc = MediaGenerationService(
                asset_store=self.store,
                enabled=True,
                confirm_cost_usd=0.5,
                image_provider_name="stub",
                openai_api_key="",
                trace_span_store=span_store,
            )
            svc.generate_image(
                prompt="trace test",
                width=64,
                height=64,
                project_id="trace-proj",
                run_id="media_run_test",
                provider="stub",
            )
            spans = span_store.list_for_run("media_run_test")
            self.assertGreaterEqual(len(spans), 1)
            self.assertEqual(spans[0]["name"], "media.generate_image")

    def test_generate_requires_confirm_for_openai_tariff(self) -> None:
        svc = MediaGenerationService(
            asset_store=self.store,
            enabled=True,
            confirm_cost_usd=0.01,
            image_provider_name="openai",
            openai_api_key="",
        )
        with self.assertRaises(MediaConfirmationRequired):
            svc.generate_image(prompt="banner", provider="openai", confirmed=False)

    def test_vision_qa_passes_stub_asset(self) -> None:
        result = self.service.generate_image(
            prompt="professional studio product shot",
            width=256,
            height=256,
            provider="stub",
        )
        qa = self.service.vision_qa_media(
            asset_id=result.asset.asset_id,
            criteria="professional studio",
            min_score=0.75,
        )
        self.assertTrue(qa.passed)
        self.assertGreaterEqual(qa.score, 0.75)

    def test_estimate_storyboard_example_under_cap(self) -> None:
        if not STORYBOARD_EXAMPLE.is_file():
            self.skipTest(f"Missing media fixture: {STORYBOARD_EXAMPLE}")
        estimate = estimate_storyboard_path(STORYBOARD_EXAMPLE)
        self.assertGreater(estimate.scene_count, 0)
        self.assertLessEqual(estimate.total_usd, 25.0)

    def test_list_media_assets_by_project(self) -> None:
        self.service.generate_image(prompt="one", project_id="p1", provider="stub")
        self.service.generate_image(prompt="two", project_id="p1", provider="stub")
        items = self.service.list_assets(project_id="p1")
        self.assertEqual(len(items), 2)

    def test_disabled_raises(self) -> None:
        off = MediaGenerationService(asset_store=self.store, enabled=False)
        with self.assertRaises(MediaStudioError):
            off.generate_image(prompt="x", provider="stub")

    def test_tools_registered(self) -> None:
        for name in ("generate_image", "vision_qa_media", "estimate_media_cost"):
            self.assertIn(name, TOOL_DEFINITIONS)
        tools = build_openai_tools(
            ["generate_image", "vision_qa_media", "estimate_media_cost", "list_media_assets"]
        )
        self.assertEqual(len(tools), 4)


class MediaApiTests(unittest.TestCase):
    def test_media_api_generate_when_enabled(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app
        from app.state import get_media_generation_service

        tmp = tempfile.TemporaryDirectory()
        try:
            service = MediaGenerationService(
                asset_store=MediaAssetStore(tmp.name),
                enabled=True,
                image_provider_name="stub",
            )
            app.dependency_overrides[get_media_generation_service] = lambda: service
            client = TestClient(app)
            response = client.post(
                "/api/media/generate-image",
                json={
                    "prompt": "API test icon",
                    "width": 128,
                    "height": 128,
                    "project_id": "api-test",
                    "provider": "stub",
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertIn("asset", body)
            self.assertEqual(body["asset"]["width"], 128)
            list_resp = client.get("/api/media/assets", params={"project_id": "api-test"})
            self.assertEqual(list_resp.status_code, 200)
            self.assertGreaterEqual(len(list_resp.json()), 1)
            if STORYBOARD_EXAMPLE.is_file():
                estimate_resp = client.post(
                    "/api/media/estimate",
                    json={"storyboard_path": str(STORYBOARD_EXAMPLE)},
                )
                self.assertEqual(estimate_resp.status_code, 200)
                self.assertLessEqual(estimate_resp.json()["total_usd"], 25.0)
        finally:
            app.dependency_overrides.clear()
            tmp.cleanup()

    def test_task_type_creative_media_enum(self) -> None:
        from app.domain.schemas import TaskType

        self.assertEqual(TaskType.creative_media.value, "creative_media")


if __name__ == "__main__":
    unittest.main()
