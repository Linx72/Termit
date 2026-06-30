"""Centralized error handler middleware for TermitPro FastAPI.

Catches ALL unhandled exceptions from routes and other middleware,
converts them to standardized JSON error responses with trace IDs.

Usage: add as the FIRST middleware so it wraps all others.
"""

from __future__ import annotations

import logging
import traceback
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.domain.exceptions import (
    TermitError,
    get_error_category,
    get_error_code,
    get_http_status,
    get_is_recoverable,
)

logger = logging.getLogger("termit.error_handler")


def _build_error_detail(exc: Exception) -> str:
    """Build a human-readable detail from an exception, stripping internal cruft."""
    # Use the exception's own str representation
    detail = str(exc) or exc.__class__.__name__
    # Trim excessively long detail (e.g. raw traceback in message)
    if len(detail) > 2000:
        detail = detail[:1997] + "..."
    return detail


def _log_exception(exc: Exception, trace_id: str, request: Request) -> None:
    """Log the exception with trace ID for debugging."""
    method = request.method if request else "?"
    path = request.url.path if request else "?"
    logger.error(
        "Unhandled error | trace_id=%s | %s %s | %s: %s",
        trace_id,
        method,
        path,
        type(exc).__name__,
        str(exc)[:200],
        exc_info=True,
    )


class ErrorHandlerMiddleware:
    """Catch-all ASGI middleware that converts any unhandled exception
    into a structured JSON error response with trace ID.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only handle HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        try:
            await self.app(scope, receive, send)
        except Exception as exc:  # noqa: BLE001 — intentional catch-all
            trace_id = str(uuid4())[:8]
            _log_exception(exc, trace_id, request)

            status_code = get_http_status(exc)
            error_code = get_error_code(exc)
            detail = _build_error_detail(exc)

            response = JSONResponse(
                status_code=status_code,
                content={
                    "error": error_code,
                    "detail": detail,
                    "category": get_error_category(exc),
                    "recoverable": get_is_recoverable(exc),
                    "trace_id": trace_id,
                },
            )
            await response(scope, receive, send)
