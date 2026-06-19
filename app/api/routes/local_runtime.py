from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    LocalModelPullRequest,
    LocalModelPullResponse,
    LocalModelsResponse,
    LocalModelsWarmResponse,
    LocalRuntimeStatusResponse,
)
from app.services.local_runtime_service import LocalRuntimeError, LocalRuntimeService
from app.state import get_local_runtime_service

router = APIRouter(prefix="/api/local", tags=["local-runtime"])


@router.get("/status", response_model=LocalRuntimeStatusResponse)
async def runtime_status(
    service: LocalRuntimeService = Depends(get_local_runtime_service),
) -> LocalRuntimeStatusResponse:
    return await service.status()


@router.get("/models", response_model=LocalModelsResponse)
async def list_local_models(
    service: LocalRuntimeService = Depends(get_local_runtime_service),
) -> LocalModelsResponse:
    try:
        return await service.list_local_models()
    except LocalRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/models/pull", response_model=LocalModelPullResponse)
async def pull_ollama_model(
    payload: LocalModelPullRequest,
    service: LocalRuntimeService = Depends(get_local_runtime_service),
) -> LocalModelPullResponse:
    try:
        return await service.pull_ollama_model(payload.model)
    except LocalRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/models/warm", response_model=LocalModelsWarmResponse)
async def warm_ollama_models(
    service: LocalRuntimeService = Depends(get_local_runtime_service),
) -> LocalModelsWarmResponse:
    from app.core.config import get_settings

    settings = get_settings()
    payload = await service.warm_ollama_models(max_models=settings.ollama_warm_max_models)
    return LocalModelsWarmResponse(**payload)
