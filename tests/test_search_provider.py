import json
import unittest
from unittest.mock import patch

from app.services.search_provider import (
    DEFAULT_SEARXNG_URL,
    CachedSearchProvider,
    PerplexitySearchProvider,
    SearxngSearchProvider,
    StubSearchProvider,
    build_search_provider,
)


class SearchProviderTests(unittest.TestCase):
    def test_stub_provider_explicit(self) -> None:
        provider = build_search_provider("", "", provider="stub")
        self.assertIsInstance(provider, StubSearchProvider)

    def test_searxng_default(self) -> None:
        provider = build_search_provider("", "", provider="searxng")
        self.assertIsInstance(provider, SearxngSearchProvider)
        self.assertEqual(provider.base_url, DEFAULT_SEARXNG_URL)

    def test_searxng_custom_base_url(self) -> None:
        provider = build_search_provider("http://search.local:9000", "", provider="searxng")
        self.assertIsInstance(provider, SearxngSearchProvider)
        self.assertEqual(provider.base_url, "http://search.local:9000")

    def test_perplexity_preset_legacy(self) -> None:
        provider = build_search_provider("", "pplx-test-key", provider="perplexity")
        self.assertIsInstance(provider, PerplexitySearchProvider)

    def test_stub_search_has_citations(self) -> None:
        result = StubSearchProvider().search("termite platform")
        self.assertTrue(result.citations)

    @patch("app.services.search_provider.urllib.request.urlopen")
    def test_searxng_parses_json_results(self, urlopen_mock) -> None:
        payload = {
            "results": [
                {
                    "title": "FastAPI docs",
                    "url": "https://fastapi.tiangolo.com/",
                    "content": "Modern web framework",
                }
            ]
        }
        response = urlopen_mock.return_value.__enter__.return_value
        response.read.return_value = json.dumps(payload).encode("utf-8")
        provider = SearxngSearchProvider("http://127.0.0.1:8888")
        result = provider.search("FastAPI middleware", max_results=3)
        self.assertEqual(result.provider, "searxng")
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.citations[0], "https://fastapi.tiangolo.com/")
        request = urlopen_mock.call_args[0][0]
        self.assertIn("/search?", request.full_url)
        self.assertIn("format=json", request.full_url)

    @patch("app.services.search_provider.urllib.request.urlopen")
    def test_searxng_domain_filter_in_query(self, urlopen_mock) -> None:
        payload = {"results": []}
        response = urlopen_mock.return_value.__enter__.return_value
        response.read.return_value = json.dumps(payload).encode("utf-8")
        provider = SearxngSearchProvider("http://127.0.0.1:8888")
        provider.search("auth middleware", domains=["github.com"], max_results=2)
        request = urlopen_mock.call_args[0][0]
        self.assertIn("site%3Agithub.com", request.full_url)

    def test_search_cache_avoids_duplicate_inner_calls(self) -> None:
        calls = 0

        class CountingProvider:
            def search(self, query: str, *, max_results: int = 5, domains=None, recency_days=None):
                nonlocal calls
                calls += 1
                return StubSearchProvider().search(query, max_results=max_results)

        inner = CountingProvider()
        cached = CachedSearchProvider(inner, ttl_seconds=60)
        cached.search("termite eval")
        cached.search("termite eval")
        self.assertEqual(calls, 1)

    def test_build_search_provider_wraps_cache_when_ttl_set(self) -> None:
        provider = build_search_provider("", "", provider="searxng", cache_ttl_seconds=120)
        self.assertIsInstance(provider, CachedSearchProvider)


if __name__ == "__main__":
    unittest.main()
