from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.schemas import (
    ApplyPatchRequest,
    ApplyPatchResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ListFilesRequest,
    ListFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
    SshConnectionTestRequest,
    SshConnectionTestResponse,
    ToolAuditEvent,
    WorkspaceScriptsResponse,
)
from app.services.ssh_workspace_service import SshWorkspaceService
from app.services.tooling_service import ToolingError, ToolingService
from app.services.workspace_scripts import (
    read_package_scripts,
    resolve_dev_server_command,
    resolve_verify_command,
)
from app.state import get_tooling_service

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/workspace-scripts", response_model=WorkspaceScriptsResponse)
async def workspace_scripts(
    workspace: str | None = Query(default=None, max_length=2000),
    tooling: ToolingService = Depends(get_tooling_service),
) -> WorkspaceScriptsResponse:
    if workspace and workspace.strip():
        root = str(Path(workspace.strip()).expanduser().resolve())
    else:
        root = str(tooling.root)
    scripts = read_package_scripts(root)
    return WorkspaceScriptsResponse(
        root=root,
        has_package_json=bool(scripts),
        scripts=scripts,
        verify_command=resolve_verify_command(root, ""),
        dev_command=resolve_dev_server_command(root),
    )


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


@router.post("/ssh/test", response_model=SshConnectionTestResponse)
async def test_ssh_connection(
    payload: SshConnectionTestRequest,
    tooling: ToolingService = Depends(get_tooling_service),
) -> SshConnectionTestResponse:
    ssh = SshWorkspaceService(tooling)
    from app.services.ssh_workspace_service import SshWorkspaceConfig

    config = SshWorkspaceConfig(
        host=payload.host.strip(),
        user=payload.user.strip(),
        remote_path=payload.remote_path.strip(),
        port=payload.port,
        identity_file=payload.identity_file.strip(),
    )
    ok, detail = ssh.test_connection(config)
    return SshConnectionTestResponse(ok=ok, detail=detail)


@router.get("/audit", response_model=list[ToolAuditEvent])
async def audit_events(
    limit: int = 100,
    tooling: ToolingService = Depends(get_tooling_service),
) -> list[ToolAuditEvent]:
    return tooling.get_audit_events(limit=limit)
