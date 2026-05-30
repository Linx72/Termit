import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.domain.schemas import (
    ChatRequest,
    ChatResponse,
    ProviderInfo,
    ProviderStatus,
    SessionClearResponse,
    SessionExportFormat,
    SessionExportResponse,
    SessionHistoryResponse,
)
from app.services.chat_service import ChatService
from app.services.providers.base import ProviderError
from app.state import get_chat_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        return await service.chat(payload)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in service.chat_stream(payload):
                yield chunk
        except ProviderError as exc:
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)}, ensure_ascii=True)}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/providers", response_model=list[ProviderInfo])
async def providers(
    service: ChatService = Depends(get_chat_service),
) -> list[ProviderInfo]:
    return service.providers_info()


@router.get("/providers/status", response_model=list[ProviderStatus])
async def providers_status(
    service: ChatService = Depends(get_chat_service),
) -> list[ProviderStatus]:
    return await service.providers_status()


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def session_history(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> SessionHistoryResponse:
    history = service.get_session_history(session_id)
    return SessionHistoryResponse(session_id=session_id, history=history)


@router.delete("/sessions/{session_id}", response_model=SessionClearResponse)
async def clear_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> SessionClearResponse:
    cleared = service.clear_session(session_id)
    return SessionClearResponse(session_id=session_id, cleared=cleared)


@router.get("/sessions/{session_id}/export", response_model=SessionExportResponse)
async def export_session(
    session_id: str,
    format: SessionExportFormat = SessionExportFormat.markdown,
    service: ChatService = Depends(get_chat_service),
) -> SessionExportResponse:
    if format == SessionExportFormat.markdown:
        content, message_count = service.export_session_markdown(session_id)
    elif format == SessionExportFormat.txt:
        content, message_count = service.export_session_txt(session_id)
    else:
        content, message_count = service.export_session_json(session_id)

    return SessionExportResponse(
        session_id=session_id,
        format=format.value,
        content=content,
        message_count=message_count,
    )
