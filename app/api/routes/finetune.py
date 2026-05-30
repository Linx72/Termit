from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.schemas import (
    FinetuneAdapterListResponse,
    FinetuneAdapterRegisterRequest,
    FinetuneAdapterResponse,
    FinetuneDatasetExportRequest,
    FinetuneDatasetExportResponse,
    FinetuneJobCreateRequest,
    FinetuneJobListResponse,
    FinetuneJobResponse,
    FinetuneRecipeResponse,
)
from app.services.finetune_service import FinetuneJobRecord, FinetuneService
from app.state import get_finetune_service

router = APIRouter(prefix="/api/finetune", tags=["finetune"])


def _job_response(job: FinetuneJobRecord) -> FinetuneJobResponse:
    return FinetuneJobResponse(
        job_id=job.job_id,
        name=job.name,
        status=job.status,
        dataset_path=job.dataset_path,
        sample_count=job.sample_count,
        base_model=job.base_model,
        created_at=job.created_at,
        updated_at=job.updated_at,
        notes=job.notes,
        adapter_model=job.adapter_model,
    )


@router.post("/datasets/export", response_model=FinetuneDatasetExportResponse)
async def export_dataset(
    payload: FinetuneDatasetExportRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneDatasetExportResponse:
    try:
        result = service.export_dataset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FinetuneDatasetExportResponse(**result)


@router.post("/jobs", response_model=FinetuneJobResponse)
async def create_job(
    payload: FinetuneJobCreateRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobResponse:
    job = service.create_job(
        name=payload.name,
        dataset_path=payload.dataset_path,
        sample_count=payload.sample_count,
        base_model=payload.base_model,
        notes=payload.notes,
    )
    return _job_response(job)


@router.get("/jobs", response_model=FinetuneJobListResponse)
async def list_jobs(
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobListResponse:
    return FinetuneJobListResponse(jobs=[_job_response(job) for job in service.list_jobs()])


@router.get("/jobs/{job_id}", response_model=FinetuneJobResponse)
async def get_job(
    job_id: str,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobResponse:
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown finetune job: {job_id}")
    return _job_response(job)


@router.post("/jobs/{job_id}/run", response_model=FinetuneJobResponse)
async def run_job(
    job_id: str,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobResponse:
    try:
        job = service.run_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(job)


@router.post("/adapters", response_model=FinetuneAdapterResponse)
async def register_adapter(
    payload: FinetuneAdapterRegisterRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneAdapterResponse:
    adapter = service.register_adapter(payload)
    return FinetuneAdapterResponse(**adapter)


@router.get("/adapters", response_model=FinetuneAdapterListResponse)
async def list_adapters(
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneAdapterListResponse:
    adapters = service.list_adapters()
    return FinetuneAdapterListResponse(
        adapters=[FinetuneAdapterResponse(**item) for item in adapters],
    )


@router.get("/recipe", response_model=FinetuneRecipeResponse)
async def training_recipe(
    base_model: str = Query(default="ollama:deepseek-coder"),
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneRecipeResponse:
    recipe = service.training_recipe(base_model)
    return FinetuneRecipeResponse(**recipe)
