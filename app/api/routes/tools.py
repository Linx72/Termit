from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    ApplyPatchRequest,
    ApplyPatchResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ListFilesRequest,
    ListFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
    ToolAuditEvent,
)
from app.services.tooling_service import ToolingError, ToolingService
from app.state import get_tooling_service

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def tool_catalog() -> dict[str, list[str]]:
    return {
        "tools": [
            "list_files(path, pattern)",
            "read_file(path, max_bytes)",
            "execute_command(command, path, timeout_seconds, dry_run, confirmed)",
            "apply_patch(path, hunks|content, create, dry_run, confirmed)",
            "audit(limit)",
        ]
    }


@router.post("/list_files", response_model=ListFilesResponse)
async def list_files(
    payload: ListFilesRequest,
    tooling: ToolingService = Depends(get_tooling_service),
) -> ListFilesResponse:
    try:
        return tooling.list_files(payload)
    except ToolingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/read_file", response_model=ReadFileResponse)
async def read_file(
    payload: ReadFileRequest,
    tooling: ToolingService = Depends(get_tooling_service),
) -> ReadFileResponse:
    try:
        return tooling.read_file(payload)
    except ToolingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute_command", response_model=ExecuteCommandResponse)
async def execute_command(
    payload: ExecuteCommandRequest,
    tooling: ToolingService = Depends(get_tooling_service),
) -> ExecuteCommandResponse:
    try:
        return tooling.execute_command(payload)
    except ToolingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/apply_patch", response_model=ApplyPatchResponse)
async def apply_patch(
    payload: ApplyPatchRequest,
    tooling: ToolingService = Depends(get_tooling_service),
) -> ApplyPatchResponse:
    try:
        return tooling.apply_patch(payload)
    except ToolingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit", response_model=list[ToolAuditEvent])
async def audit_events(
    limit: int = 100,
    tooling: ToolingService = Depends(get_tooling_service),
) -> list[ToolAuditEvent]:
    return tooling.get_audit_events(limit=limit)
