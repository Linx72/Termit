from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.platform import router as platform_router
from app.services.search_provider import StubSearchProvider
from app.state import get_search_provider


class PlatformSearchTests(unittest.TestCase):
    def test_search_web_returns_hits(self) -> None:
        app = FastAPI()
        app.include_router(platform_router)
        app.dependency_overrides[get_search_provider] = lambda: StubSearchProvider()
        client = TestClient(app)
        response = client.post(
            "/api/platform/search",
            json={"query": "FastAPI middleware auth", "max_results": 3},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["query"], "FastAPI middleware auth")
        self.assertGreaterEqual(len(payload["hits"]), 1)
        self.assertEqual(payload["provider"], "stub")


if __name__ == "__main__":
    unittest.main()
