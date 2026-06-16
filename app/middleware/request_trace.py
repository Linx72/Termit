from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.state import get_telemetry_store

logger = logging.getLogger("termit.request")


class RequestTraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id")
        if not trace_id:
            trace_id = f"tr_{uuid4().hex[:16]}"
        request.state.trace_id = trace_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            path = request.url.path
            if path.startswith("/api/"):
                try:
                    get_telemetry_store().record_http_request(
                        method=request.method,
                        path=path,
                        status_code=status_code,
                        latency_ms=latency_ms,
                    )
                except Exception:  # noqa: BLE001
                    pass
            logger.info(
                "%s %s -> %s (%sms)",
                request.method,
                path,
                status_code,
                latency_ms,
                extra={
                    "event": "http_request",
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                },
            )
