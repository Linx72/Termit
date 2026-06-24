"""
FTS5-поиск по сообщениям чата в сессиях.
GET /api/sessions/{session_id}/search?q=...
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.services.chat_service import ChatService
from app.state import get_chat_service

router = APIRouter(prefix="/api/sessions", tags=["session-search"])


class SearchMatch(BaseModel):
    session_id: str
    role: str
    content_snippet: str  # ±100 chars around match
    match_position: int   # character offset in message


class SearchResult(BaseModel):
    query: str
    session_id: str
    total_matches: int
    matches: list[SearchMatch]


@router.get("/{session_id}/search", response_model=SearchResult)
async def search_session_messages(
    session_id: str,
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    service: ChatService = Depends(get_chat_service),
) -> SearchResult:
    """
    Полнотекстовый поиск по сообщениям в сессии.
    
    Использует SQLite FTS5 для быстрого поиска.
    Возвращает сниппеты с контекстом ±100 символов.
    """
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    try:
        matches = service.search_session_messages(session_id, q, limit)
        return SearchResult(
            query=q,
            session_id=session_id,
            total_matches=len(matches),
            matches=matches,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=list[SearchMatch])
async def search_all_sessions(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(default=30, ge=1, le=200),
    service: ChatService = Depends(get_chat_service),
) -> list[SearchMatch]:
    """
    Поиск по всем сессиям (глобальный FTS5).
    Возвращает до 200 совпадений.
    """
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    return service.search_all_sessions(q, limit)
