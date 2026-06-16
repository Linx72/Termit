"""Media Studio orchestration: image generation, QA, cost estimate."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional
from uuid import uuid4

import time

from app.services.media_brand_kit_store import BrandKitRecord, BrandKitStore
from app.services.media_gif_service import MediaGifService
from app.services.media_lottie_service import MediaLottieError, MediaLottieService
from app.services.media_job_store import MediaJobRecord, MediaJobStore
from app.services.media_compose_service import (
    MediaComposeError,
    MediaComposeService,
    load_timeline_file,
    parse_timeline,
)
from app.services.media_cost_service import MediaCostEstimate, estimate_from_storyboard, estimate_storyboard_path
from app.services.media_png_util import write_solid_png
from app.services.media_provider_openai import MediaProviderError, OpenAIImageProvider
from app.services.media_provider_transcribe import MediaTranscribeError, OpenAITranscribeProvider
from app.services.media_provider_tts import MediaTtsError, OpenAITtsProvider
from app.services.media_provider_video import FalVideoProvider, MediaVideoError, StubVideoProvider
from app.services.trace_span_store import TraceSpanStore


class MediaStudioError(Exception):
    pass


class MediaConfirmationRequired(MediaStudioError):
    """Cloud generation blocked until confirmed=true."""


@dataclass(frozen=True)
class GenerateImageResult:
    asset: MediaAssetRecord
    revised_prompt: Optional[str] = None

    def to_observation(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "asset_id": self.asset.asset_id,
            "path": self.asset.rel_path,
            "mime": self.asset.mime,
            "width": self.asset.width,
            "height": self.asset.height,
            "provider": self.asset.provider,
            "cost_usd": self.asset.cost_usd,
        }
        if self.revised_prompt:
            payload["revised_prompt"] = self.revised_prompt
        return payload


@dataclass(frozen=True)
class VisionQaResult:
    score: float
    passed: bool
    notes: str

    def to_observation(self) -> dict[str, object]:
        return {"score": self.score, "passed": self.passed, "notes": self.notes}


@dataclass(frozen=True)
class ComposeMediaResult:
    asset: MediaAssetRecord
    duration_sec: float

    def to_observation(self) -> dict[str, object]:
        return {
            "asset_id": self.asset.asset_id,
            "path": self.asset.rel_path,
            "mime": self.asset.mime,
            "duration_sec": self.duration_sec,
            "provider": self.asset.provider,
        }


@dataclass(frozen=True)
class TtsGenerateResult:
    asset: MediaAssetRecord

    def to_observation(self) -> dict[str, object]:
        return {
            "asset_id": self.asset.asset_id,
            "path": self.asset.rel_path,
            "mime": self.asset.mime,
            "provider": self.asset.provider,
            "cost_usd": self.asset.cost_usd,
        }


@dataclass(frozen=True)
class TranscribeMediaResult:
    asset: MediaAssetRecord
    language: str

    def to_observation(self) -> dict[str, object]:
        return {
            "asset_id": self.asset.asset_id,
            "path": self.asset.rel_path,
            "mime": self.asset.mime,
            "language": self.language,
            "provider": self.asset.provider,
        }


class MediaGenerationService:
    def __init__(
        self,
        *,
        asset_store: MediaAssetStore,
        enabled: bool = True,
        max_cost_usd: float = 25.0,
        confirm_cost_usd: float = 1.0,
        image_provider_name: str = "openai",
        openai_api_key: str = "",
        openai_base_url: str = "https://api.openai.com/v1",
        openai_image_model: str = "dall-e-3",
        image_cost_usd: float = 0.08,
        tts_cost_usd: float = 0.015,
        transcribe_cost_usd: float = 0.006,
        tts_voice: str = "alloy",
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        jobs_db_path: str = "./data/media/media_jobs.db",
        i2v_provider: str = "stub",
        fal_api_key: str = "",
        media_public_base_url: str = "",
        i2v_cost_usd: float = 0.50,
        brand_kits_dir: str = "./data/media/brand_kits",
        run_cost_ledger: Optional[dict[str, float]] = None,
        trace_span_store: Optional[TraceSpanStore] = None,
    ) -> None:
        self._store = asset_store
        self._trace_spans = trace_span_store
        self._enabled = enabled
        self._max_cost = max(0.0, max_cost_usd)
        self._confirm_threshold = max(0.0, confirm_cost_usd)
        self._image_provider_name = image_provider_name.strip().lower() or "stub"
        self._image_cost_usd = image_cost_usd
        self._openai = OpenAIImageProvider(
            api_key=openai_api_key,
            base_url=openai_base_url,
            image_model=openai_image_model,
            default_cost_usd=image_cost_usd,
        )
        self._tts = OpenAITtsProvider(
            api_key=openai_api_key,
            base_url=openai_base_url,
            default_voice=tts_voice,
            default_cost_usd=tts_cost_usd,
        )
        self._transcribe = OpenAITranscribeProvider(
            api_key=openai_api_key,
            base_url=openai_base_url,
            default_cost_usd=transcribe_cost_usd,
        )
        self._compose = MediaComposeService(ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)
        self._gif = MediaGifService(ffmpeg_path=ffmpeg_path)
        self._lottie = MediaLottieService()
        self._stub_video = StubVideoProvider(ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)
        self._fal_video = FalVideoProvider(api_key=fal_api_key, default_cost_usd=i2v_cost_usd)
        self._jobs = MediaJobStore(jobs_db_path)
        self._brand_kits = BrandKitStore(brand_kits_dir)
        self._i2v_provider = i2v_provider.strip().lower() or "stub"
        self._media_public_base_url = media_public_base_url.strip().rstrip("/")
        self._i2v_cost = i2v_cost_usd
        self._ffmpeg_path = ffmpeg_path
        self._ffprobe_path = ffprobe_path
        self._tts_cost = tts_cost_usd
        self._run_ledger = run_cost_ledger if run_cost_ledger is not None else {}

    def _ensure_enabled(self) -> None:
        if not self._enabled:
            raise MediaStudioError("Media Studio is disabled (TERMIT_MEDIA_ENABLED=false).")

    def _resolve_fal_image_url(self, *, source_asset_id: str, image_path: Path) -> str:
        if self._media_public_base_url:
            return f"{self._media_public_base_url}/api/media/assets/{source_asset_id}/file"
        try:
            return self._fal_video.upload_local_image(image_path)
        except MediaVideoError as exc:
            raise MediaStudioError(str(exc)) from exc

    def _record_media_span(
        self,
        *,
        run_id: Optional[str],
        name: str,
        status: str,
        detail: str = "",
        duration_ms: int = 0,
    ) -> None:
        if self._trace_spans is None or not run_id:
            return
        self._trace_spans.record(
            run_id=run_id,
            name=name,
            status=status,
            detail=detail[:500],
            duration_ms=max(0, duration_ms),
        )

    @contextmanager
    def _media_trace(self, *, run_id: Optional[str], name: str) -> Iterator[dict[str, str]]:
        started = time.perf_counter()
        meta: dict[str, str] = {"detail": ""}
        try:
            yield meta
        except Exception as exc:
            self._record_media_span(
                run_id=run_id,
                name=name,
                status="error",
                detail=str(exc)[:500],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        else:
            self._record_media_span(
                run_id=run_id,
                name=name,
                status="ok",
                detail=meta.get("detail", ""),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

    def _ledger_add(self, run_id: Optional[str], cost: float) -> float:
        if not run_id:
            return cost
        total = self._run_ledger.get(run_id, 0.0) + cost
        self._run_ledger[run_id] = total
        if total > self._max_cost:
            raise MediaStudioError(
                f"Run media cost ${total:.2f} exceeds cap TERMIT_MEDIA_MAX_COST_USD={self._max_cost:.2f}."
            )
        return total

    def estimate_cost(
        self,
        *,
        storyboard_path: Optional[str] = None,
        storyboard: Optional[dict[str, object]] = None,
    ) -> MediaCostEstimate:
        self._ensure_enabled()
        if storyboard is not None:
            return estimate_from_storyboard(storyboard)
        if storyboard_path:
            return estimate_storyboard_path(storyboard_path)
        raise MediaStudioError("estimate_media_cost requires storyboard_path or storyboard.")

    def generate_image(
        self,
        *,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        project_id: str = "default",
        run_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        provider: Optional[str] = None,
        confirmed: bool = False,
        output_name: Optional[str] = None,
    ) -> GenerateImageResult:
        self._ensure_enabled()
        with self._media_trace(run_id=run_id, name="media.generate_image") as meta:
            clean_prompt = prompt.strip()
            if not clean_prompt:
                raise MediaStudioError("generate_image requires non-empty prompt.")
            chosen = (provider or self._image_provider_name).strip().lower()
            est_cost = self._image_cost_usd if chosen == "openai" else 0.0
            if est_cost >= self._confirm_threshold and not confirmed:
                raise MediaConfirmationRequired(
                    f"Image generation est. ${est_cost:.2f} requires confirmed=true "
                    f"(threshold ${self._confirm_threshold:.2f})."
                )
            assets_dir = self._store.project_dir(project_id)
            filename = output_name or f"{scene_id or 'img'}_{uuid4().hex[:8]}.png"
            if not filename.endswith(".png"):
                filename += ".png"
            target = assets_dir / filename

            revised: Optional[str] = None
            if chosen == "openai" and self._openai.available:
                try:
                    gen = self._openai.generate(prompt=clean_prompt, width=width, height=height)
                except MediaProviderError as exc:
                    raise MediaStudioError(str(exc)) from exc
                target.write_bytes(gen.bytes_data)
                provider_used = gen.provider
                cost = gen.cost_usd
                revised = gen.revised_prompt
            else:
                write_solid_png(target, width, height, (30, 64, 175))
                provider_used = "stub"
                cost = 0.0

            self._ledger_add(run_id, cost)
            record = self._store.register_file(
                project_id=project_id,
                file_path=target,
                mime="image/png",
                provider=provider_used,
                cost_usd=cost,
                prompt=clean_prompt,
                run_id=run_id,
                scene_id=scene_id,
            )
            self._store.append_audit(
                {
                    "action": "generate_image",
                    "asset_id": record.asset_id,
                    "provider": provider_used,
                    "cost_usd": cost,
                    "run_id": run_id,
                    "project_id": project_id,
                }
            )
            meta["detail"] = f"provider={provider_used}, asset={record.asset_id}, cost={cost:.4f}"
            return GenerateImageResult(asset=record, revised_prompt=revised)

    def list_assets(
        self,
        *,
        project_id: Optional[str] = None,
        run_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[MediaAssetRecord]:
        self._ensure_enabled()
        return self._store.list_assets(
            project_id=project_id,
            run_id=run_id,
            scene_id=scene_id,
            limit=limit,
        )

    def vision_qa_media(
        self,
        *,
        asset_id: str,
        criteria: str = "",
        min_score: float = 0.75,
    ) -> VisionQaResult:
        self._ensure_enabled()
        record = self._store.get_asset(asset_id)
        if record is None:
            raise MediaStudioError(f"Unknown asset_id: {asset_id}")
        path = self._store.resolve_path(record)
        if not path.is_file():
            raise MediaStudioError(f"Asset file missing: {path}")
        score = 0.85
        notes: list[str] = []
        if record.width <= 0 or record.height <= 0:
            score -= 0.3
            notes.append("Could not read image dimensions.")
        else:
            notes.append(f"Dimensions {record.width}x{record.height} OK.")
        criteria_lower = criteria.lower()
        prompt_lower = record.prompt.lower()
        if criteria_lower and any(
            token in prompt_lower
            for token in criteria_lower.split()
            if len(token) > 4
        ):
            score += 0.05
            notes.append("Prompt overlaps criteria keywords.")
        if record.mime != "image/png":
            score -= 0.1
            notes.append(f"Unexpected mime {record.mime}.")
        score = max(0.0, min(1.0, score))
        passed = score >= min_score
        if not passed:
            notes.append(f"Score {score:.2f} below min_score {min_score:.2f}.")
        return VisionQaResult(score=score, passed=passed, notes=" ".join(notes))

    def get_asset_bytes(self, asset_id: str) -> tuple[MediaAssetRecord, bytes]:
        record = self._store.get_asset(asset_id)
        if record is None:
            raise MediaStudioError(f"Unknown asset_id: {asset_id}")
        path = self._store.resolve_path(record)
        return record, path.read_bytes()

    def resolve_asset_path(self, asset_id: str) -> Path:
        record = self._store.get_asset(asset_id)
        if record is None:
            raise MediaStudioError(f"Unknown asset_id: {asset_id}")
        return self._store.resolve_path(record)

    def tts_generate(
        self,
        *,
        text: str,
        project_id: str = "default",
        run_id: Optional[str] = None,
        voice_id: Optional[str] = None,
        language: str = "ru",
        confirmed: bool = False,
        provider: Optional[str] = None,
    ) -> TtsGenerateResult:
        self._ensure_enabled()
        chosen = (provider or "openai").strip().lower()
        est_cost = self._tts_cost if chosen == "openai" and self._tts.available else 0.0
        if est_cost >= self._confirm_threshold and not confirmed:
            raise MediaConfirmationRequired(
                f"TTS est. ${est_cost:.2f} requires confirmed=true "
                f"(threshold ${self._confirm_threshold:.2f})."
            )
        try:
            result = self._tts.synthesize(text=text, voice=voice_id, language=language)
        except MediaTtsError as exc:
            raise MediaStudioError(str(exc)) from exc
        exports_dir = self._store.project_dir(project_id)
        target = exports_dir / f"vo_{uuid4().hex[:8]}.wav"
        target.write_bytes(result.bytes_data)
        self._ledger_add(run_id, result.cost_usd)
        record = self._store.register_file(
            project_id=project_id,
            file_path=target,
            mime=result.mime,
            provider=result.provider,
            cost_usd=result.cost_usd,
            prompt=text[:4000],
            run_id=run_id,
        )
        self._store.append_audit(
            {
                "action": "tts_generate",
                "asset_id": record.asset_id,
                "provider": result.provider,
                "cost_usd": result.cost_usd,
                "run_id": run_id,
            }
        )
        return TtsGenerateResult(asset=record)

    def transcribe_media(
        self,
        *,
        asset_id: str,
        project_id: str = "default",
        run_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> TranscribeMediaResult:
        self._ensure_enabled()
        record = self._store.get_asset(asset_id)
        if record is None:
            raise MediaStudioError(f"Unknown asset_id: {asset_id}")
        media_path = self._store.resolve_path(record)
        try:
            result = self._transcribe.transcribe(media_path=media_path, language=language)
        except MediaTranscribeError as exc:
            raise MediaStudioError(str(exc)) from exc
        exports_dir = self._store.project_dir(project_id)
        target = exports_dir / f"subs_{uuid4().hex[:8]}.srt"
        target.write_text(result.srt_text, encoding="utf-8")
        self._ledger_add(run_id, result.cost_usd)
        sub_record = self._store.register_file(
            project_id=project_id,
            file_path=target,
            mime="text/srt",
            provider=result.provider,
            cost_usd=result.cost_usd,
            prompt=f"transcribe:{asset_id}",
            run_id=run_id,
        )
        self._store.append_audit(
            {
                "action": "transcribe_media",
                "source_asset_id": asset_id,
                "asset_id": sub_record.asset_id,
                "provider": result.provider,
                "cost_usd": result.cost_usd,
                "run_id": run_id,
            }
        )
        return TranscribeMediaResult(asset=sub_record, language=result.language)

    def compose_media(
        self,
        *,
        project_id: str = "default",
        run_id: Optional[str] = None,
        timeline_path: Optional[str] = None,
        timeline: Optional[dict[str, object]] = None,
        output_name: Optional[str] = None,
        preset: str = "youtube_16x9",
    ) -> ComposeMediaResult:
        self._ensure_enabled()
        if timeline is None:
            if timeline_path:
                timeline = load_timeline_file(Path(timeline_path))
            else:
                raise MediaStudioError("compose_media requires timeline or timeline_path.")
        slides_raw, timeline_preset, crossfade, audio_id, subtitle_id = parse_timeline(timeline)
        chosen_preset = str(timeline.get("preset", timeline_preset or preset))
        slides: list[dict[str, object]] = []
        for item in slides_raw:
            if "path" in item:
                slides.append(
                    {
                        "path": str(item["path"]),
                        "duration_sec": float(item.get("duration_sec", 3)),
                    }
                )
                continue
            asset_id = str(item.get("asset_id", ""))
            asset = self._store.get_asset(asset_id)
            if asset is None:
                raise MediaStudioError(f"Unknown slide asset_id: {asset_id}")
            slides.append(
                {
                    "path": str(self._store.resolve_path(asset)),
                    "duration_sec": float(item.get("duration_sec", 3)),
                }
            )
        audio_path: Optional[Path] = None
        if audio_id:
            audio_rec = self._store.get_asset(audio_id)
            if audio_rec is None:
                raise MediaStudioError(f"Unknown audio_asset_id: {audio_id}")
            audio_path = self._store.resolve_path(audio_rec)
        subtitle_path: Optional[Path] = None
        if subtitle_id:
            sub_rec = self._store.get_asset(subtitle_id)
            if sub_rec is None:
                raise MediaStudioError(f"Unknown subtitle_asset_id: {subtitle_id}")
            subtitle_path = self._store.resolve_path(sub_rec)

        exports_dir = self._store.root.resolve() / _project_slug(project_id) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        out_name = output_name or timeline.get("output_name") or f"master_{uuid4().hex[:8]}.mp4"
        if not str(out_name).endswith(".mp4"):
            out_name = f"{out_name}.mp4"
        output_path = exports_dir / str(out_name)
        try:
            composed = self._compose.compose_slideshow(
                slides=slides,
                output_path=output_path,
                preset=chosen_preset,
                crossfade_sec=crossfade,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
            )
        except MediaComposeError as exc:
            raise MediaStudioError(str(exc)) from exc
        record = self._store.register_file(
            project_id=project_id,
            file_path=output_path,
            mime="video/mp4",
            provider="ffmpeg",
            cost_usd=0.0,
            prompt=f"compose:{len(slides)} slides",
            run_id=run_id,
        )
        self._store.append_audit(
            {
                "action": "compose_media",
                "asset_id": record.asset_id,
                "duration_sec": composed.duration_sec,
                "run_id": run_id,
            }
        )
        return ComposeMediaResult(asset=record, duration_sec=composed.duration_sec)

    def render_video(
        self,
        *,
        prompt: str,
        project_id: str = "default",
        run_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        source_asset_id: Optional[str] = None,
        mode: str = "image_to_video",
        duration_sec: float = 5.0,
        provider: Optional[str] = None,
        confirmed: bool = False,
    ) -> MediaJobRecord:
        self._ensure_enabled()
        chosen = (provider or self._i2v_provider).strip().lower()
        est = self._i2v_cost if chosen == "fal" else 0.0
        if est >= self._confirm_threshold and not confirmed:
            raise MediaConfirmationRequired(
                f"render_video est. ${est:.2f} requires confirmed=true."
            )
        payload: dict[str, object] = {
            "prompt": prompt,
            "mode": mode,
            "source_asset_id": source_asset_id,
            "duration_sec": duration_sec,
            "scene_id": scene_id,
        }
        job = self._jobs.create(
            job_type="render_video",
            provider=chosen,
            payload=payload,
            project_id=project_id,
            run_id=run_id,
            cost_usd=0.0,
        )
        self._jobs.update(job.job_id, status="running")
        try:
            asset_id = self._execute_render_job(
                job=job,
                prompt=prompt,
                project_id=project_id,
                run_id=run_id,
                scene_id=scene_id,
                source_asset_id=source_asset_id,
                duration_sec=duration_sec,
                provider=chosen,
            )
            updated = self._jobs.update(
                job.job_id,
                status="completed",
                result_asset_id=asset_id,
                cost_usd=est if chosen == "fal" else 0.0,
            )
            self._ledger_add(run_id, est if chosen == "fal" else 0.0)
            assert updated is not None
            return updated
        except Exception as exc:  # noqa: BLE001
            self._jobs.update(job.job_id, status="failed", error=str(exc))
            raise MediaStudioError(str(exc)) from exc

    def _execute_render_job(
        self,
        *,
        job: MediaJobRecord,
        prompt: str,
        project_id: str,
        run_id: Optional[str],
        scene_id: Optional[str],
        source_asset_id: Optional[str],
        duration_sec: float,
        provider: str,
    ) -> str:
        exports = self._store.root.resolve() / _project_slug(project_id) / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        out_path = exports / f"clip_{scene_id or job.job_id}.mp4"
        if not source_asset_id:
            raise MediaStudioError("render_video image_to_video requires source_asset_id.")
        source = self._store.get_asset(source_asset_id)
        if source is None:
            raise MediaStudioError(f"Unknown source_asset_id: {source_asset_id}")
        image_path = self._store.resolve_path(source)
        if provider == "fal" and self._fal_video.available:
            image_url = self._resolve_fal_image_url(
                source_asset_id=source_asset_id,
                image_path=image_path,
            )
            try:
                result = self._fal_video.render_image_to_video(
                    image_url=image_url,
                    prompt=prompt,
                    output_path=out_path,
                    duration_sec=duration_sec,
                )
            except MediaVideoError as exc:
                raise MediaStudioError(str(exc)) from exc
            record = self._store.register_file(
                project_id=project_id,
                file_path=out_path,
                mime="video/mp4",
                provider=result.provider,
                cost_usd=result.cost_usd,
                prompt=prompt,
                run_id=run_id,
                scene_id=scene_id,
            )
            self._store.append_audit(
                {"action": "render_video", "job_id": job.job_id, "asset_id": record.asset_id}
            )
            return record.asset_id
        result = self._stub_video.render_image_to_video(
            image_path=image_path,
            output_path=out_path,
            duration_sec=duration_sec,
        )
        record = self._store.register_file(
            project_id=project_id,
            file_path=out_path,
            mime="video/mp4",
            provider=result.provider,
            cost_usd=result.cost_usd,
            prompt=prompt,
            run_id=run_id,
            scene_id=scene_id,
        )
        self._store.append_audit(
            {"action": "render_video", "job_id": job.job_id, "asset_id": record.asset_id}
        )
        return record.asset_id

    def wait_media_job(
        self,
        *,
        job_id: str,
        timeout_sec: int = 600,
    ) -> MediaJobRecord:
        self._ensure_enabled()
        _ = timeout_sec  # sync jobs complete immediately in v1
        record = self._jobs.get(job_id)
        if record is None:
            raise MediaStudioError(f"Unknown job_id: {job_id}")
        if record.status == "failed":
            raise MediaStudioError(record.error or "Media job failed")
        return record

    def get_media_job(self, job_id: str) -> MediaJobRecord:
        record = self._jobs.get(job_id)
        if record is None:
            raise MediaStudioError(f"Unknown job_id: {job_id}")
        return record

    def export_gif(
        self,
        *,
        asset_ids: list[str],
        project_id: str = "default",
        run_id: Optional[str] = None,
        fps: int = 8,
        width: int = 480,
        output_name: Optional[str] = None,
    ) -> MediaAssetRecord:
        self._ensure_enabled()
        if not asset_ids:
            raise MediaStudioError("export_gif requires asset_ids.")
        paths: list[Path] = []
        for aid in asset_ids:
            rec = self._store.get_asset(aid)
            if rec is None:
                raise MediaStudioError(f"Unknown asset_id: {aid}")
            paths.append(self._store.resolve_path(rec))
        exports = self._store.root.resolve() / _project_slug(project_id) / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        name = output_name or f"anim_{uuid4().hex[:8]}.gif"
        if not name.endswith(".gif"):
            name += ".gif"
        out_path = exports / name
        try:
            self._gif.export_gif(image_paths=paths, output_path=out_path, fps=fps, width=width)
        except MediaComposeError as exc:
            raise MediaStudioError(str(exc)) from exc
        record = self._store.register_file(
            project_id=project_id,
            file_path=out_path,
            mime="image/gif",
            provider="ffmpeg",
            cost_usd=0.0,
            prompt=f"gif:{len(asset_ids)} frames",
            run_id=run_id,
        )
        return record

    def export_lottie(
        self,
        *,
        asset_ids: list[str],
        project_id: str = "default",
        run_id: Optional[str] = None,
        fps: int = 8,
        width: int = 480,
        output_name: Optional[str] = None,
    ) -> MediaAssetRecord:
        self._ensure_enabled()
        if not asset_ids:
            raise MediaStudioError("export_lottie requires asset_ids.")
        paths: list[Path] = []
        for aid in asset_ids:
            rec = self._store.get_asset(aid)
            if rec is None:
                raise MediaStudioError(f"Unknown asset_id: {aid}")
            paths.append(self._store.resolve_path(rec))
        exports = self._store.root.resolve() / _project_slug(project_id) / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        name = output_name or f"anim_{uuid4().hex[:8]}.json"
        if not name.endswith(".json"):
            name += ".json"
        out_path = exports / name
        try:
            self._lottie.export_lottie(image_paths=paths, output_path=out_path, fps=fps, width=width)
        except MediaLottieError as exc:
            raise MediaStudioError(str(exc)) from exc
        record = self._store.register_file(
            project_id=project_id,
            file_path=out_path,
            mime="application/json",
            provider="lottie",
            cost_usd=0.0,
            prompt=f"lottie:{len(asset_ids)} frames",
            run_id=run_id,
        )
        return record

    def list_brand_kits(self) -> list[BrandKitRecord]:
        self._ensure_enabled()
        return self._brand_kits.list_kits()

    def get_brand_kit(self, brand_kit_id: str) -> BrandKitRecord:
        self._ensure_enabled()
        kit = self._brand_kits.get(brand_kit_id)
        if kit is None:
            raise MediaStudioError(f"Unknown brand_kit_id: {brand_kit_id}")
        return kit

    def run_storyboard(
        self,
        *,
        storyboard_path: Optional[str] = None,
        storyboard: Optional[dict[str, object]] = None,
        project_id: str = "default",
        run_id: Optional[str] = None,
        brand_kit_id: Optional[str] = None,
        max_scenes: int = 6,
        confirmed: bool = False,
    ) -> ComposeMediaResult:
        """Studio-pack helper: images → optional I2V → compose master MP4."""
        self._ensure_enabled()
        with self._media_trace(run_id=run_id, name="media.run_storyboard") as meta:
            if storyboard is None:
                if not storyboard_path:
                    raise MediaStudioError("run_storyboard requires storyboard or path.")
                storyboard = json.loads(Path(storyboard_path).read_text(encoding="utf-8"))
                if not isinstance(storyboard, dict):
                    raise MediaStudioError("Storyboard must be a JSON object.")
            style_suffix = ""
            if brand_kit_id:
                kit = self.get_brand_kit(brand_kit_id)
                style_suffix = kit.style_prompt_suffix
            scenes = storyboard.get("scenes", [])
            if not isinstance(scenes, list):
                raise MediaStudioError("storyboard.scenes invalid")
            clips: list[dict[str, object]] = []
            vo_chunks: list[str] = []
            for raw in scenes[: max(1, max_scenes)]:
                if not isinstance(raw, dict):
                    continue
                scene_id = str(raw.get("scene_id", "scene"))
                visual = str(raw.get("visual_prompt", ""))
                if style_suffix:
                    visual = f"{visual}. {style_suffix}"
                mode = str(raw.get("render_mode", "image_to_video"))
                duration = float(raw.get("duration_sec", 3))
                img = self.generate_image(
                    prompt=visual,
                    project_id=project_id,
                    run_id=run_id,
                    scene_id=scene_id,
                    provider="stub",
                    confirmed=confirmed,
                )
                vo = str(raw.get("voiceover", "")).strip()
                if vo:
                    vo_chunks.append(vo)
                if mode == "image_to_video":
                    job = self.render_video(
                        prompt=visual,
                        project_id=project_id,
                        run_id=run_id,
                        scene_id=scene_id,
                        source_asset_id=img.asset.asset_id,
                        duration_sec=min(duration, 8.0),
                        confirmed=confirmed,
                    )
                    if job.result_asset_id:
                        clips.append({"asset_id": job.result_asset_id, "duration_sec": duration})
                    continue
                clips.append({"asset_id": img.asset.asset_id, "duration_sec": duration})
            audio_id: Optional[str] = None
            if vo_chunks:
                vo = self.tts_generate(
                    text=" ".join(vo_chunks),
                    project_id=project_id,
                    run_id=run_id,
                    confirmed=confirmed,
                )
                audio_id = vo.asset.asset_id
            preset = str(storyboard.get("aspect_ratio", "16:9"))
            preset_map = {"16:9": "youtube_16x9", "9:16": "reels_9x16", "1:1": "telegram_1x1"}
            result = self.compose_media(
                project_id=project_id,
                run_id=run_id,
                timeline={
                    "preset": preset_map.get(preset, "youtube_16x9"),
                    "crossfade_sec": 0,
                    "clips": clips,
                    "audio_asset_id": audio_id,
                    "output_name": "storyboard_master.mp4",
                },
            )
            meta["detail"] = f"scenes={len(clips)}, asset={result.asset.asset_id}"
            return result


def _project_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "default"
