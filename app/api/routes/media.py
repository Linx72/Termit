"""Media Studio API — images, compose, TTS, transcription."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.domain.schemas import (
    MediaAssetResponse,
    MediaComposeRequest,
    MediaComposeResponse,
    BrandKitResponse,
    MediaExportGifRequest,
    MediaJobResponse,
    MediaRenderVideoRequest,
    MediaStoryboardRunRequest,
    MediaEstimateCostRequest,
    MediaEstimateCostResponse,
    MediaCostLineResponse,
    MediaGenerateImageRequest,
    MediaGenerateImageResponse,
    MediaTranscribeRequest,
    MediaTranscribeResponse,
    MediaTtsRequest,
    MediaTtsResponse,
    MediaVisionQaRequest,
    MediaVisionQaResponse,
)
from app.services.media_generation_service import MediaConfirmationRequired, MediaStudioError
from app.state import get_media_generation_service

router = APIRouter(prefix="/api/media", tags=["media"])


def _asset_response(record) -> MediaAssetResponse:
    return MediaAssetResponse(**record.to_dict())


@router.get("/assets", response_model=list[MediaAssetResponse])
async def list_media_assets(
    project_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    scene_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service=Depends(get_media_generation_service),
) -> list[MediaAssetResponse]:
    try:
        items = service.list_assets(project_id=project_id, run_id=run_id, scene_id=scene_id, limit=limit)
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_asset_response(item) for item in items]


@router.get("/assets/{asset_id}/file")
async def download_media_asset(
    asset_id: str,
    service=Depends(get_media_generation_service),
):
    try:
        path = service.resolve_asset_path(asset_id)
        record, _data = service.get_asset_bytes(asset_id)
    except MediaStudioError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return FileResponse(path, media_type=record.mime, filename=path.name)


@router.post("/generate-image", response_model=MediaGenerateImageResponse)
async def generate_image(
    payload: MediaGenerateImageRequest,
    service=Depends(get_media_generation_service),
) -> MediaGenerateImageResponse:
    try:
        result = service.generate_image(
            prompt=payload.prompt,
            width=payload.width,
            height=payload.height,
            project_id=payload.project_id,
            run_id=payload.run_id,
            scene_id=payload.scene_id,
            provider=payload.provider,
            confirmed=payload.confirmed,
        )
    except MediaConfirmationRequired as exc:
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaGenerateImageResponse(
        asset=_asset_response(result.asset),
        revised_prompt=result.revised_prompt,
    )


@router.post("/estimate", response_model=MediaEstimateCostResponse)
async def estimate_media_cost(
    payload: MediaEstimateCostRequest,
    service=Depends(get_media_generation_service),
) -> MediaEstimateCostResponse:
    try:
        if not payload.storyboard_path:
            raise MediaStudioError("storyboard_path is required")
        estimate = service.estimate_cost(storyboard_path=payload.storyboard_path)
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaEstimateCostResponse(
        total_usd=estimate.total_usd,
        scene_count=estimate.scene_count,
        lines=[
            MediaCostLineResponse(scene_id=line.scene_id, item=line.item, usd=line.usd)
            for line in estimate.lines
        ],
    )


@router.post("/vision-qa", response_model=MediaVisionQaResponse)
async def vision_qa_media(
    payload: MediaVisionQaRequest,
    service=Depends(get_media_generation_service),
) -> MediaVisionQaResponse:
    try:
        result = service.vision_qa_media(
            asset_id=payload.asset_id,
            criteria=payload.criteria,
            min_score=payload.min_score,
        )
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaVisionQaResponse(score=result.score, passed=result.passed, notes=result.notes)


@router.post("/tts", response_model=MediaTtsResponse)
async def tts_generate(
    payload: MediaTtsRequest,
    service=Depends(get_media_generation_service),
) -> MediaTtsResponse:
    try:
        result = service.tts_generate(
            text=payload.text,
            project_id=payload.project_id,
            run_id=payload.run_id,
            voice_id=payload.voice_id,
            language=payload.language,
            confirmed=payload.confirmed,
        )
    except MediaConfirmationRequired as exc:
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaTtsResponse(asset=_asset_response(result.asset))


@router.post("/transcribe", response_model=MediaTranscribeResponse)
async def transcribe_media(
    payload: MediaTranscribeRequest,
    service=Depends(get_media_generation_service),
) -> MediaTranscribeResponse:
    try:
        result = service.transcribe_media(
            asset_id=payload.asset_id,
            project_id=payload.project_id,
            run_id=payload.run_id,
            language=payload.language,
        )
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaTranscribeResponse(asset=_asset_response(result.asset), language=result.language)


@router.post("/compose", response_model=MediaComposeResponse)
async def compose_media(
    payload: MediaComposeRequest,
    service=Depends(get_media_generation_service),
) -> MediaComposeResponse:
    try:
        result = service.compose_media(
            project_id=payload.project_id,
            run_id=payload.run_id,
            timeline_path=payload.timeline_path,
            timeline=payload.timeline,
            output_name=payload.output_name,
            preset=payload.preset,
        )
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaComposeResponse(
        asset=_asset_response(result.asset),
        duration_sec=result.duration_sec,
    )


def _job_response(record) -> MediaJobResponse:
    data = record.to_dict()
    return MediaJobResponse(**data)


@router.get("/jobs/{job_id}", response_model=MediaJobResponse)
async def get_media_job(
    job_id: str,
    service=Depends(get_media_generation_service),
) -> MediaJobResponse:
    try:
        job = service.get_media_job(job_id)
    except MediaStudioError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _job_response(job)


@router.post("/render-video", response_model=MediaJobResponse)
async def render_video(
    payload: MediaRenderVideoRequest,
    service=Depends(get_media_generation_service),
) -> MediaJobResponse:
    try:
        job = service.render_video(
            prompt=payload.prompt,
            source_asset_id=payload.source_asset_id,
            project_id=payload.project_id,
            run_id=payload.run_id,
            scene_id=payload.scene_id,
            duration_sec=payload.duration_sec,
            provider=payload.provider,
            confirmed=payload.confirmed,
        )
    except MediaConfirmationRequired as exc:
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(job)


@router.post("/export-gif", response_model=MediaAssetResponse)
async def export_gif(
    payload: MediaExportGifRequest,
    service=Depends(get_media_generation_service),
) -> MediaAssetResponse:
    try:
        asset = service.export_gif(
            asset_ids=payload.asset_ids,
            project_id=payload.project_id,
            run_id=payload.run_id,
            fps=payload.fps,
            width=payload.width,
        )
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _asset_response(asset)


@router.post("/run-storyboard", response_model=MediaComposeResponse)
async def run_storyboard(
    payload: MediaStoryboardRunRequest,
    service=Depends(get_media_generation_service),
) -> MediaComposeResponse:
    try:
        result = service.run_storyboard(
            storyboard_path=payload.storyboard_path,
            storyboard=payload.storyboard,
            project_id=payload.project_id,
            run_id=payload.run_id,
            brand_kit_id=payload.brand_kit_id,
            max_scenes=payload.max_scenes,
            confirmed=payload.confirmed,
        )
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaComposeResponse(
        asset=_asset_response(result.asset),
        duration_sec=result.duration_sec,
    )


@router.get("/brand-kits", response_model=list[BrandKitResponse])
async def list_brand_kits(
    service=Depends(get_media_generation_service),
) -> list[BrandKitResponse]:
    try:
        kits = service.list_brand_kits()
    except MediaStudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [BrandKitResponse(**kit.to_dict()) for kit in kits]


@router.get("/brand-kits/{brand_kit_id}", response_model=BrandKitResponse)
async def get_brand_kit(
    brand_kit_id: str,
    service=Depends(get_media_generation_service),
) -> BrandKitResponse:
    try:
        kit = service.get_brand_kit(brand_kit_id)
    except MediaStudioError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BrandKitResponse(**kit.to_dict())
