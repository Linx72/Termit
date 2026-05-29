from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    TaskCancelResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskEvent,
    TaskStatusResponse,
)
from app.services.task_service import TaskNotFoundError, TaskService
from app.state import get_task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreateResponse)
async def create_task(
    payload: TaskCreateRequest,
    service: TaskService = Depends(get_task_service),
) -> TaskCreateResponse:
    return service.create_task(payload)


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskStatusResponse:
    try:
        return service.get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}/events", response_model=list[TaskEvent])
async def get_task_events(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> list[TaskEvent]:
    try:
        return service.get_task_events(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
async def cancel_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskCancelResponse:
    try:
        return service.cancel_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
