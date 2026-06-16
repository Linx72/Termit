import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.domain.schemas import (
    AgentProfileCreateRequest,
    AgentProfileResponse,
    AgentRunCancelResponse,
    AgentRunConfirmRequest,
    AgentRunConfirmResponse,
    AgentRunResumeResponse,
    AgentRunCreateResponse,
    AgentRunDlqReplayResponse,
    AgentRunEvent,
    AgentRunListResponse,
    AgentRunRecordResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunState,
    AgentMemoryListResponse,
    ApplyPatchRequest,
    ApplyPatchResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ListFilesRequest,
    ListFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
    WebAutomationRequest,
    WebAutomationResponse,
)
from app.services.agent_service import (
    AgentOnlineError,
    AgentNotFoundError,
    AgentPermissionError,
    AgentQueueFullError,
    AgentDrainingError,
    AgentRunNotFoundError,
    AgentService,
    GuardrailBlockedError,
)
from app.services.agent_run_notifier import AgentRunNotifier
from app.services.tooling_service import ToolingError
from app.services.providers.base import ProviderError
from app.state import get_agent_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentProfileResponse])
async def list_agents(
    service: AgentService = Depends(get_agent_service),
) -> list[AgentProfileResponse]:
    return service.list_agents()


@router.post("", response_model=AgentProfileResponse)
async def create_agent(
    payload: AgentProfileCreateRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentProfileResponse:
    return service.create_agent(payload)


@router.get("/{agent_id}", response_model=AgentProfileResponse)
async def get_agent(
    agent_id: str,
    service: AgentService = Depends(get_agent_service),
) -> AgentProfileResponse:
    try:
        return service.get_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{agent_id}/memory", response_model=AgentMemoryListResponse)
async def list_agent_memory(
    agent_id: str,
    limit: int = 20,
    service: AgentService = Depends(get_agent_service),
) -> AgentMemoryListResponse:
    try:
        entries = service.list_agent_memory(agent_id, limit=limit)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AgentMemoryListResponse(entries=entries)


@router.post("/{agent_id}/run", response_model=AgentRunResponse)
async def run_agent(
    agent_id: str,
    payload: AgentRunRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunResponse:
    try:
        return await service.run_agent(agent_id, payload)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentOnlineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{agent_id}/runs", response_model=AgentRunCreateResponse)
async def create_agent_run(
    agent_id: str,
    payload: AgentRunRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunCreateResponse:
    try:
        return service.create_run(agent_id, payload)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentQueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AgentDrainingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GuardrailBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{agent_id}/runs", response_model=AgentRunListResponse)
async def list_agent_runs(
    agent_id: str,
    limit: int = 50,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunListResponse:
    try:
        service.get_agent(agent_id)
        return service.list_runs(agent_id=agent_id, limit=limit)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/children", response_model=AgentRunListResponse)
async def list_child_runs(
    run_id: str,
    limit: int = 50,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunListResponse:
    try:
        service.get_run(run_id)
        return service.list_child_runs(run_id, limit=limit)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/dlq", response_model=AgentRunListResponse)
async def list_dlq_runs(
    limit: int = 50,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunListResponse:
    return service.list_dlq_runs(limit=limit)


@router.post("/runs/dlq/replay", response_model=AgentRunDlqReplayResponse)
async def replay_dlq_runs(
    limit: int = 5,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunDlqReplayResponse:
    replayed = service.replay_dlq(limit=limit)
    return AgentRunDlqReplayResponse(replayed=replayed, count=len(replayed))


@router.post("/runs/{run_id}/replay", response_model=AgentRunCreateResponse)
async def replay_agent_run(
    run_id: str,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunCreateResponse:
    try:
        return service.replay_run(run_id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=AgentRunRecordResponse)
async def get_agent_run(
    run_id: str,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunRecordResponse:
    try:
        return service.get_run(run_id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/events", response_model=list[AgentRunEvent])
async def get_agent_run_events(
    run_id: str,
    limit: int = 500,
    service: AgentService = Depends(get_agent_service),
) -> list[AgentRunEvent]:
    try:
        return service.get_run_events(run_id, limit=limit)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel", response_model=AgentRunCancelResponse)
async def cancel_agent_run(
    run_id: str,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunCancelResponse:
    try:
        return service.cancel_run(run_id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/confirm", response_model=AgentRunConfirmResponse)
async def confirm_agent_run(
    run_id: str,
    payload: AgentRunConfirmRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunConfirmResponse:
    try:
        return service.confirm_run(run_id, approved=payload.approved)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentQueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/resume", response_model=AgentRunResumeResponse)
async def resume_agent_run(
    run_id: str,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunResumeResponse:
    try:
        return service.resume_run(run_id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentQueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}/stream")
async def stream_agent_run(
    run_id: str,
    poll_ms: int = 400,
    timeout_seconds: int = 120,
    service: AgentService = Depends(get_agent_service),
) -> StreamingResponse:
    safe_poll_seconds = max(0.5, min(poll_ms, 5000) / 1000.0)
    safe_timeout = max(5, min(timeout_seconds, 600))
    notifier = AgentRunNotifier.get()

    async def event_generator() -> AsyncIterator[str]:
        try:
            run = service.get_run(run_id)
        except AgentRunNotFoundError:
            payload = {"detail": f"Agent run not found: {run_id}"}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
            yield "event: done\ndata: {}\n\n"
            return

        events = service.get_run_events(run_id, limit=500)
        yield f"event: status\ndata: {json.dumps(run.model_dump(mode='json'), ensure_ascii=True)}\n\n"
        for event in events:
            yield f"event: timeline\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=True)}\n\n"

        if run.state in {
            AgentRunState.completed,
            AgentRunState.failed,
            AgentRunState.cancelled,
            AgentRunState.awaiting_confirmation,
        }:
            yield "event: done\ndata: {}\n\n"
            return

        queue = notifier.subscribe(run_id)
        deadline = asyncio.get_running_loop().time() + safe_timeout
        try:
            while True:
                now = asyncio.get_running_loop().time()
                if now >= deadline:
                    yield "event: timeout\ndata: {}\n\n"
                    yield "event: done\ndata: {}\n\n"
                    break
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=safe_poll_seconds)
                except asyncio.TimeoutError:
                    try:
                        run = service.get_run(run_id)
                    except AgentRunNotFoundError:
                        break
                    if run.state in {
                        AgentRunState.completed,
                        AgentRunState.failed,
                        AgentRunState.cancelled,
                        AgentRunState.awaiting_confirmation,
                    }:
                        yield f"event: status\ndata: {json.dumps(run.model_dump(mode='json'), ensure_ascii=True)}\n\n"
                        yield "event: done\ndata: {}\n\n"
                        break
                    continue

                if kind == "status":
                    yield f"event: status\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
                    if payload.get("terminal"):
                        yield "event: done\ndata: {}\n\n"
                        break
                elif kind == "timeline":
                    yield f"event: timeline\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
        finally:
            notifier.unsubscribe(run_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{agent_id}/tools/list_files", response_model=ListFilesResponse)
async def list_files_as_agent(
    agent_id: str,
    payload: ListFilesRequest,
    service: AgentService = Depends(get_agent_service),
) -> ListFilesResponse:
    try:
        return service.list_files_as_agent(agent_id, payload)
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (AgentNotFoundError, ToolingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{agent_id}/tools/read_file", response_model=ReadFileResponse)
async def read_file_as_agent(
    agent_id: str,
    payload: ReadFileRequest,
    service: AgentService = Depends(get_agent_service),
) -> ReadFileResponse:
    try:
        return service.read_file_as_agent(agent_id, payload)
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (AgentNotFoundError, ToolingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{agent_id}/tools/execute_command", response_model=ExecuteCommandResponse)
async def execute_command_as_agent(
    agent_id: str,
    payload: ExecuteCommandRequest,
    service: AgentService = Depends(get_agent_service),
) -> ExecuteCommandResponse:
    try:
        return service.execute_command_as_agent(agent_id, payload)
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (AgentNotFoundError, ToolingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{agent_id}/tools/apply_patch", response_model=ApplyPatchResponse)
async def apply_patch_as_agent(
    agent_id: str,
    payload: ApplyPatchRequest,
    service: AgentService = Depends(get_agent_service),
) -> ApplyPatchResponse:
    try:
        return service.apply_patch_as_agent(agent_id, payload)
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (AgentNotFoundError, ToolingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{agent_id}/tools/web_automation", response_model=WebAutomationResponse)
async def run_web_automation_as_agent(
    agent_id: str,
    payload: WebAutomationRequest,
    service: AgentService = Depends(get_agent_service),
) -> WebAutomationResponse:
    try:
        return service.run_online_as_agent(agent_id, payload)
    except AgentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (AgentNotFoundError, AgentOnlineError, ToolingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
