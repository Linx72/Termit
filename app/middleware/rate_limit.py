"""Per-endpoint rate limiting middleware for TermitPro FastAPI.

Uses in-memory sliding window counters keyed on (client_ip, endpoint).
Configurable per-endpoint limits via settings.rate_limit_endpoints.

Architecture: this runs BEFORE AuthQuotaMiddleware so it can protect
unauthenticated endpoints like /api/login and /api/register.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("termit.rate_limit")


def _now_sec() -> float:
    return time.monotonic()


class SlidingWindow:
    """Fixed-window counter with expiry for a single (ip, endpoint) pair."""

    __slots__ = ("window_sec", "max_requests", "timestamps")

    def __init__(self, window_sec: float, max_requests: int) -> None:
        self.window_sec = window_sec
        self.max_requests = max_requests
        self.timestamps: list[float] = []

    def allow(self) -> bool:
        """Return True if the request is within limits."""
        now = _now_sec()
        cutoff = now - self.window_sec
        # Prune expired timestamps
        while self.timestamps and self.timestamps[0] <= cutoff:
            self.timestamps.pop(0)
        if len(self.timestamps) < self.max_requests:
            self.timestamps.append(now)
            return True
        return False


class RateLimitMiddleware:
    """ASGI middleware enforcing per-endpoint rate limits.

    Checks every HTTP request against configured limits by endpoint.
    Wraps only the error handler so rate-limit rejections follow the
    same JSON error format as the rest of the app.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_window_sec: float = 60.0,
        default_max_requests: int = 30,
        endpoint_limits: dict[str, dict[str, int]] | None = None,
    ) -> None:
        self.app = app
        self.default_window_sec = default_window_sec
        self.default_max_requests = default_max_requests
        self.endpoint_limits: dict[str, dict[str, int]] = endpoint_limits or {}
        # (ip, normalized_path) -> SlidingWindow
        self._windows: dict[tuple[str, str], SlidingWindow] = {}
        self._recently_cleaned_at: float = _now_sec()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # --- resolve limits for this endpoint ---
        path = request.url.path.rstrip("/")
        limits: dict[str, int] | None = None
        for prefix, cfg in self.endpoint_limits.items():
            if path.startswith(prefix):
                limits = cfg
                break

        if limits is None:
            # No explicit limit for this endpoint → allow through
            await self.app(scope, receive, send)
            return

        window_sec = float(limits.get("window_sec", self.default_window_sec))
        max_req = int(limits.get("max_requests", self.default_max_requests))

        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, path)

        # --- check / increment window ---
        window = self._windows.get(key)
        if window is None:
            window = SlidingWindow(window_sec, max_req)
            self._windows[key] = window

        if window.allow():
            # --- periodic cleanup to prevent memory leak ---
            now = _now_sec()
            if now - self._recently_cleaned_at > 300:  # every 5 min
                self._cleanup(now)
            await self.app(scope, receive, send)
            return

        # --- rate limit exceeded ---
        logger.warning(
            "Rate limit exceeded | path=%s | ip=%s | window=%ss max=%d",
            path, client_ip, window_sec, max_req,
        )
        response = JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "detail": f"Too many requests to {path}. Try again in {window_sec}s.",
                "category": "rate_limit",
                "recoverable": True,
                "retry_after_sec": window_sec,
            },
            headers={"Retry-After": str(int(window_sec))},
        )
        await response(scope, receive, send)

    def _cleanup(self, now: float) -> None:
        """Remove windows with no recent activity."""
        cutoff = now - max(
            self.default_window_sec,
            *(int(c.get("window_sec", self.default_window_sec))
              for c in self.endpoint_limits.values()),
        )
        stale_keys = [
            key
            for key, w in self._windows.items()
            if not w.timestamps or w.timestamps[-1] <= cutoff
        ]
        for key in stale_keys:
            del self._windows[key]
        self._recently_cleaned_at = now
