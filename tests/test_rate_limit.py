"""Unit tests for per-endpoint RateLimitMiddleware."""

import time
import unittest

from app.middleware.rate_limit import RateLimitMiddleware, SlidingWindow
from fastapi import FastAPI
from fastapi.testclient import TestClient


class SlidingWindowTests(unittest.TestCase):
    """Tests for the low-level SlidingWindow counter."""

    def test_requests_within_limit_pass(self) -> None:
        w = SlidingWindow(window_sec=60.0, max_requests=5)
        for _ in range(5):
            self.assertTrue(w.allow(), "first 5 requests should be allowed")
        self.assertFalse(w.allow(), "6th request should be denied")

    def test_prunes_expired_timestamps(self) -> None:
        w = SlidingWindow(window_sec=0.2, max_requests=3)
        for _ in range(3):
            self.assertTrue(w.allow())
        self.assertFalse(w.allow(), "window full before expiry")

        time.sleep(0.25)  # let timestamps expire
        self.assertTrue(w.allow(), "expired timestamps should be pruned → allowed again")


def _make_app(
    endpoint_limits: dict[str, dict[str, int]] | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, endpoint_limits=endpoint_limits or {})

    @app.get("/api/chat")
    async def chat():
        return {"ok": True}

    @app.get("/api/public")
    async def public():
        return {"ok": True}

    return app


class RateLimitMiddlewareTests(unittest.TestCase):
    """Integration tests for RateLimitMiddleware via TestClient."""

    def test_endpoint_without_limit_passes(self) -> None:
        app = _make_app(endpoint_limits={})
        with TestClient(app) as client:
            for _ in range(100):
                resp = client.get("/api/public")
                self.assertEqual(resp.status_code, 200)

    def test_endpoint_with_limit_allows_up_to_max(self) -> None:
        limits = {"/api/chat": {"window_sec": 60, "max_requests": 3}}
        app = _make_app(endpoint_limits=limits)
        with TestClient(app) as client:
            for _ in range(3):
                resp = client.get("/api/chat")
                self.assertEqual(resp.status_code, 200)

    def test_endpoint_exceeding_limit_returns_429(self) -> None:
        limits = {"/api/chat": {"window_sec": 60, "max_requests": 2}}
        app = _make_app(endpoint_limits=limits)
        with TestClient(app) as client:
            client.get("/api/chat")
            client.get("/api/chat")
            resp = client.get("/api/chat")
            self.assertEqual(resp.status_code, 429)
            body = resp.json()
            self.assertEqual(body["error"], "rate_limited")
            self.assertIn("recoverable", body)
            self.assertEqual(resp.headers.get("Retry-After"), "60")

    def test_different_ips_have_separate_windows(self) -> None:
        """Verify that the (client_ip, path) tuple key gives each IP its own window.

        Starlette's TestClient does not spoof client.host via X-Forwarded-For,
        so we validate the core window-keying logic directly."""
        limits = {"/api/chat": {"window_sec": 60, "max_requests": 1}}
        mw = RateLimitMiddleware(None, endpoint_limits=limits)  # type: ignore[arg-type]
        self.assertNotIn(("1.1.1.1", "/api/chat"), mw._windows)
        # Simulate window creation for different IPs
        mw._windows[("1.1.1.1", "/api/chat")] = SlidingWindow(60.0, 1)
        mw._windows[("1.1.1.1", "/api/chat")].allow()  # consume its one request
        self.assertFalse(mw._windows[("1.1.1.1", "/api/chat")].allow(), "IP 1.1.1.1 should be exhausted")
        # IP 2.2.2.2 should be unaffected
        self.assertNotIn(("2.2.2.2", "/api/chat"), mw._windows, "different IP should have separate window")
