"""
API-роутер для BraveSearch MCP.

Предоставляет 6 эндпоинтов поиска + регистрацию в plugin_tools.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.brave_search_mcp import (
    BraveSearchMcpError,
    BraveSearchResult,
    get_brave_search_client,
)
from app.services.agent_tool_schema import deferred_tool_catalog

_logger = logging.getLogger("termit.brave_search_routes")

router = APIRouter(prefix="/api/brave", tags=["brave-search"])

# ── Схемы инструментов для регистрации ───────────────────────────

_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "brave_web_search": {
        "type": "function",
        "function": {
            "name": "brave_web_search",
            "description": "Поиск в интернете через Brave Search API. Возвращает веб-результаты: ссылки, заголовки, описания.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос (макс 400 символов, 50 слов)"},
                    "count": {"type": "integer", "description": "Количество результатов (1-20, по умолчанию 10)"},
                    "country": {"type": "string", "description": "Код страны (например: RU, US, DE)"},
                    "search_lang": {"type": "string", "description": "Язык поиска (например: ru, en)"},
                },
                "required": ["query"],
            },
        },
    },
    "brave_local_search": {
        "type": "function",
        "function": {
            "name": "brave_local_search",
            "description": "Поиск локальных бизнесов и POI (точки интереса) через Brave Search API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос (рестораны, магазины и т.д.)"},
                    "count": {"type": "integer", "description": "Количество результатов (1-20, по умолчанию 5)"},
                    "country": {"type": "string", "description": "Код страны"},
                },
                "required": ["query"],
            },
        },
    },
    "brave_image_search": {
        "type": "function",
        "function": {
            "name": "brave_image_search",
            "description": "Поиск изображений через Brave Search API. Возвращает URL картинок, размеры, источники.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос для изображений"},
                    "count": {"type": "integer", "description": "Количество результатов (1-20, по умолчанию 10)"},
                    "safe_search": {
                        "type": "string",
                        "enum": ["off", "moderate", "strict"],
                        "description": "Фильтр контента: off, moderate, strict",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "brave_video_search": {
        "type": "function",
        "function": {
            "name": "brave_video_search",
            "description": "Поиск видео через Brave Search API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос для видео"},
                    "count": {"type": "integer", "description": "Количество результатов (1-20, по умолчанию 10)"},
                },
                "required": ["query"],
            },
        },
    },
    "brave_news_search": {
        "type": "function",
        "function": {
            "name": "brave_news_search",
            "description": "Поиск новостей через Brave Search API. Фильтрация по свежести.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос для новостей"},
                    "count": {"type": "integer", "description": "Количество результатов (1-20, по умолчанию 10)"},
                    "freshness": {
                        "type": "string",
                        "enum": ["pd", "pw", "pm", "py"],
                        "description": "Свежесть: последний день (pd), неделя (pw), месяц (pm), год (py)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "brave_place_search": {
        "type": "function",
        "function": {
            "name": "brave_place_search",
            "description": "Поиск мест (гео-локации) через Brave Search API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Название места, адрес или достопримечательность"},
                    "country": {"type": "string", "description": "Код страны"},
                    "search_lang": {"type": "string", "description": "Язык поиска"},
                },
                "required": ["query"],
            },
        },
    },
}


def _register_tools() -> None:
    """Зарегистрировать инструменты в deferred_tool_catalog."""
    registered = 0
    for name, schema in _TOOL_SCHEMAS.items():
        if name not in deferred_tool_catalog:
            deferred_tool_catalog[name] = schema
            registered += 1
    if registered:
        _logger.info("Зарегистрировано %d инструментов BraveSearch в каталоге", registered)


# ── Эндпоинты ─────────────────────────────────────────────────────


@router.post("/web_search")
async def brave_web_search(
    query: str = Query(..., description="Поисковый запрос"),
    count: int = Query(10, ge=1, le=20, description="Количество результатов"),
    offset: int = Query(0, ge=0, le=9, description="Смещение для пагинации"),
    country: str = Query("", description="Код страны"),
    search_lang: str = Query("", description="Язык поиска"),
) -> dict[str, Any]:
    """Веб-поиск Brave Search."""
    try:
        client = await get_brave_search_client()
        results = await client.web_search(query, count, offset, country, search_lang)
        return {"status": "ok", "query": query, "results": results, "total": len(results)}
    except BraveSearchMcpError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        _logger.exception("Ошибка веб-поиска")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/local_search")
async def brave_local_search(
    query: str = Query(..., description="Поисковый запрос"),
    count: int = Query(5, ge=1, le=20),
    country: str = Query(""),
) -> dict[str, Any]:
    """Локальный поиск (бизнес/POI)."""
    try:
        client = await get_brave_search_client()
        results = await client.local_search(query, count, country)
        return {"status": "ok", "query": query, "results": results, "total": len(results)}
    except BraveSearchMcpError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/image_search")
async def brave_image_search(
    query: str = Query(..., description="Поисковый запрос"),
    count: int = Query(10, ge=1, le=20),
    safe_search: str = Query("moderate", pattern="^(off|moderate|strict)$"),
) -> dict[str, Any]:
    """Поиск изображений."""
    try:
        client = await get_brave_search_client()
        results = await client.image_search(query, count, safe_search=safe_search)
        return {"status": "ok", "query": query, "results": results, "total": len(results)}
    except BraveSearchMcpError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/video_search")
async def brave_video_search(
    query: str = Query(..., description="Поисковый запрос"),
    count: int = Query(10, ge=1, le=20),
) -> dict[str, Any]:
    """Поиск видео."""
    try:
        client = await get_brave_search_client()
        results = await client.video_search(query, count)
        return {"status": "ok", "query": query, "results": results, "total": len(results)}
    except BraveSearchMcpError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/news_search")
async def brave_news_search(
    query: str = Query(..., description="Поисковый запрос"),
    count: int = Query(10, ge=1, le=20),
    freshness: str = Query("", pattern="^(|pd|pw|pm|py)$"),
) -> dict[str, Any]:
    """Поиск новостей."""
    try:
        client = await get_brave_search_client()
        results = await client.news_search(query, count, freshness)
        return {"status": "ok", "query": query, "results": results, "total": len(results)}
    except BraveSearchMcpError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/place_search")
async def brave_place_search(
    query: str = Query(..., description="Название места"),
    country: str = Query(""),
    search_lang: str = Query(""),
) -> dict[str, Any]:
    """Поиск мест."""
    try:
        client = await get_brave_search_client()
        results = await client.place_search(query, country, search_lang)
        return {"status": "ok", "query": query, "results": results, "total": len(results)}
    except BraveSearchMcpError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/tools")
async def list_brave_tools() -> dict[str, Any]:
    """Список доступных инструментов BraveSearch."""
    return {
        "tools": list(_TOOL_SCHEMAS.keys()),
        "total": len(_TOOL_SCHEMAS),
    }


@router.get("/health")
async def brave_health() -> dict[str, str]:
    """Проверка доступности BraveSearch MCP."""
    try:
        client = await get_brave_search_client()
        return {"status": "ok", "provider": "brave_search_mcp"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── Регистрация при импорте ───────────────────────────────────────

_register_tools()
