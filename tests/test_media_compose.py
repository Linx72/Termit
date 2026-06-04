"""Media Studio Phase 2 — compose, TTS, transcribe."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from app.services.media_asset_store import MediaAssetStore
from app.services.media_compose_service import MediaComposeService, ffmpeg_available
from app.services.media_generation_service import MediaGenerationService
from app.services.agent_tool_schema import TOOL_DEFINITIONS


class MediaPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = MediaAssetStore(self._tmp.name)
        self.service = MediaGenerationService(
            asset_store=self.store,
            enabled=True,
            image_provider_name="stub",
            openai_api_key="",
            ffmpeg_path="ffmpeg",
            ffprobe_path="ffprobe",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_phase2_tools_registered(self) -> None:
        for name in ("tts_generate", "transcribe_media", "compose_media"):
            self.assertIn(name, TOOL_DEFINITIONS)

    def test_tts_generate_stub(self) -> None:
        result = self.service.tts_generate(
            text="Termit Media Studio voiceover test.",
            project_id="p2",
        )
        path = self.store.resolve_path(result.asset)
        self.assertTrue(path.is_file())
        self.assertEqual(result.asset.mime, "audio/wav")

    def test_transcribe_stub(self) -> None:
        tts = self.service.tts_generate(text="hello", project_id="p2")
        tr = self.service.transcribe_media(
            asset_id=tts.asset.asset_id,
            project_id="p2",
        )
        srt_path = self.store.resolve_path(tr.asset)
        self.assertTrue(srt_path.is_file())
        self.assertIn("stub", srt_path.read_text(encoding="utf-8").lower())

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg not installed")
    def test_compose_slideshow_from_images(self) -> None:
        slides = []
        asset_ids = []
        for idx in range(3):
            img = self.service.generate_image(
                prompt=f"slide {idx}",
                width=640,
                height=360,
                project_id="compose-test",
                provider="stub",
            )
            asset_ids.append(img.asset.asset_id)
            slides.append({"asset_id": img.asset.asset_id, "duration_sec": 1.5})

        composed = self.service.compose_media(
            project_id="compose-test",
            timeline={
                "preset": "youtube_16x9",
                "crossfade_sec": 0.2,
                "clips": slides,
                "output_name": "test_slideshow.mp4",
            },
        )
        path = self.store.resolve_path(composed.asset)
        self.assertTrue(path.is_file())
        self.assertGreater(composed.duration_sec, 0.0)
        self.assertEqual(composed.asset.mime, "video/mp4")

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg not installed")
    def test_compose_with_audio(self) -> None:
        img = self.service.generate_image(
            prompt="single",
            width=320,
            height=240,
            project_id="av-test",
            provider="stub",
        )
        vo = self.service.tts_generate(text="Audio track", project_id="av-test")
        composed = self.service.compose_media(
            project_id="av-test",
            timeline={
                "preset": "youtube_16x9",
                "clips": [{"asset_id": img.asset.asset_id, "duration_sec": 2}],
                "audio_asset_id": vo.asset.asset_id,
            },
        )
        self.assertGreater(composed.duration_sec, 0.0)


class MediaComposeServiceUnitTests(unittest.TestCase):
    @unittest.skipUnless(ffmpeg_available(), "ffmpeg not installed")
    def test_compose_service_direct(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        try:
            store = MediaAssetStore(tmp.name)
            svc = MediaGenerationService(
                asset_store=store,
                enabled=True,
                image_provider_name="stub",
            )
            img_path = store.project_dir("direct") / "frame.png"
            from app.services.media_png_util import write_solid_png

            write_solid_png(img_path, 320, 240, (255, 0, 0))
            out = store.root / "direct" / "exports" / "out.mp4"
            compose = MediaComposeService()
            result = compose.compose_slideshow(
                slides=[{"path": str(img_path), "duration_sec": 1}],
                output_path=out,
                preset="youtube_16x9",
                crossfade_sec=0,
            )
            self.assertTrue(result.output_path.is_file())
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
