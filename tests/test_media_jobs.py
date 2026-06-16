"""Media Studio phases 3–4: jobs, I2V stub, GIF, storyboard."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from app.services.media_asset_store import MediaAssetStore
from app.services.media_compose_service import ffmpeg_available
from app.services.media_generation_service import MediaGenerationService

ROOT = Path(__file__).resolve().parents[1]
STORYBOARD_EXAMPLE = ROOT / "data/media/examples/storyboard.example.json"
MEDIA_EVAL_SCENARIOS = ROOT / "data/eval_scenarios_media.json"


class MediaJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.service = MediaGenerationService(
            asset_store=MediaAssetStore(self._tmp.name),
            enabled=True,
            image_provider_name="stub",
            jobs_db_path=f"{self._tmp.name}/jobs.db",
            ffmpeg_path="ffmpeg",
            ffprobe_path="ffprobe",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg required")
    def test_render_video_stub_i2v(self) -> None:
        img = self.service.generate_image(prompt="hero", width=640, height=360, provider="stub")
        job = self.service.render_video(
            prompt="zoom in",
            source_asset_id=img.asset.asset_id,
            duration_sec=2,
            confirmed=True,
        )
        self.assertEqual(job.status, "completed")
        waited = self.service.wait_media_job(job_id=job.job_id)
        self.assertTrue(waited.result_asset_id)
        asset = self.service.get_media_job(job.job_id)
        self.assertIsNotNone(asset.result_asset_id)

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg required")
    def test_export_gif(self) -> None:
        ids = [
            self.service.generate_image(prompt=f"f{i}", width=128, height=128, provider="stub").asset.asset_id
            for i in range(3)
        ]
        gif = self.service.export_gif(asset_ids=ids, fps=4, width=200)
        self.assertEqual(gif.mime, "image/gif")
        path = self.service.resolve_asset_path(gif.asset_id)
        self.assertTrue(path.is_file())

    def test_export_lottie(self) -> None:
        ids = [
            self.service.generate_image(prompt=f"l{i}", width=128, height=128, provider="stub").asset.asset_id
            for i in range(3)
        ]
        lottie = self.service.export_lottie(asset_ids=ids, fps=4, width=128)
        self.assertEqual(lottie.mime, "application/json")
        path = self.service.resolve_asset_path(lottie.asset_id)
        self.assertTrue(path.is_file())
        payload = path.read_text(encoding="utf-8")
        self.assertIn('"layers"', payload)
        self.assertIn('"assets"', payload)

    def test_fal_image_url_public_base(self) -> None:
        service = MediaGenerationService(
            asset_store=MediaAssetStore(self._tmp.name),
            enabled=True,
            image_provider_name="stub",
            jobs_db_path=f"{self._tmp.name}/jobs2.db",
            media_public_base_url="https://media.example.com",
        )
        img = service.generate_image(prompt="hero", width=64, height=64, provider="stub")
        source = service._store.get_asset(img.asset.asset_id)
        self.assertIsNotNone(source)
        image_path = service._store.resolve_path(source)
        url = service._resolve_fal_image_url(
            source_asset_id=img.asset.asset_id,
            image_path=image_path,
        )
        self.assertEqual(
            url,
            f"https://media.example.com/api/media/assets/{img.asset.asset_id}/file",
        )

    @unittest.skipUnless(ffmpeg_available(), "ffmpeg required")
    def test_run_storyboard_short(self) -> None:
        if not STORYBOARD_EXAMPLE.is_file():
            self.skipTest(f"Missing media fixture: {STORYBOARD_EXAMPLE}")
        master = self.service.run_storyboard(
            storyboard_path=str(STORYBOARD_EXAMPLE),
            project_id="eval-story",
            brand_kit_id="termit-default",
            max_scenes=2,
            confirmed=True,
        )
        self.assertEqual(master.asset.mime, "video/mp4")
        self.assertGreater(master.duration_sec, 0)

    def test_list_brand_kits(self) -> None:
        kits = self.service.list_brand_kits()
        if not kits:
            self.skipTest("Brand kit fixtures are not available in this checkout")
        ids = {k.brand_kit_id for k in kits}
        self.assertIn("termit-default", ids)


class MediaEvalIntegrationTests(unittest.TestCase):
    def test_media_eval_scenarios_ms1_ms4(self) -> None:
        if not MEDIA_EVAL_SCENARIOS.is_file():
            self.skipTest(f"Missing media eval scenarios: {MEDIA_EVAL_SCENARIOS}")
        from app.services.eval_service import EvalService

        ev = EvalService(extra_scenarios_path=str(MEDIA_EVAL_SCENARIOS))
        for sid in ("MS1", "MS2", "MS3", "MS4"):
            result = ev.run_scenario(sid)
            self.assertEqual(result["status"], "passed", result)


if __name__ == "__main__":
    unittest.main()
