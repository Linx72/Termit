from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from threading import Lock
from typing import Optional, Protocol


DEFAULT_SEARXNG_URL = "http://127.0.0.1:8888"
PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"
EXA_SEARCH_URL = "https://api.exa.ai/search"


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    score: float = 1.0


@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: list[SearchHit]
    provider: str
    citations: list[str]

    def to_observation(self) -> str:
        lines = [f"[web_search] query={self.query!r} provider={self.provider}"]
        for index, hit in enumerate(self.hits, start=1):
            lines.append(f"[{index}] {hit.title}")
            lines.append(f"    url: {hit.url}")
            lines.append(f"    snippet: {hit.snippet[:400]}")
        return "\n".join(lines)


class SearchProvider(Protocol):
    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        domains: Optional[list[str]] = None,
        recency_days: Optional[int] = None,
    ) -> SearchResult: ...


class CachedSearchProvider:
    """TTL cache for web search — снижает дублирующие запросы в tool loop."""

    def __init__(self, inner: SearchProvider, ttl_seconds: int = 300) -> None:
        self._inner = inner
        self._ttl = max(1, ttl_seconds)
        self._cache: dict[str, tuple[float, SearchResult]] = {}
        self._lock = Lock()

    def _cache_key(
        self,
        query: str,
        max_results: int,
        domains: Optional[list[str]],
        recency_days: Optional[int],
    ) -> str:
        dom = ",".join(sorted(domain.strip() for domain in (domains or []) if domain.strip()))
        return f"{query.strip()}|{max_results}|{dom}|{recency_days}"

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        domains: Optional[list[str]] = None,
        recency_days: Optional[int] = None,
    ) -> SearchResult:
        key = self._cache_key(query, max_results, domains, recency_days)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and now - cached[0] < self._ttl:
                return cached[1]
        result = self._inner.search(
            query,
            max_results=max_results,
            domains=domains,
            recency_days=recency_days,
        )
        with self._lock:
            self._cache[key] = (now, result)
        return result


class StubSearchProvider:
    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        domains: Optional[list[str]] = None,
        recency_days: Optional[int] = None,
    ) -> SearchResult:
        _ = domains, recency_days
        hits = [
            SearchHit(
                title=f"Stub result for {query[:40]}",
                url="https://example.com/docs",
                snippet=(
                    "Offline stub search provider. "
                    "Start SearXNG or set TERMIT_SEARCH_API_URL for live results."
                ),
            )
        ][: max(1, max_results)]
        citations = [hit.url for hit in hits]
        return SearchResult(query=query, hits=hits, provider="stub", citations=citations)


class SearxngSearchProvider:
    """Self-hosted meta-search via SearXNG JSON API (GET /search?format=json)."""

    provider_label = "searxng"

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        domains: Optional[list[str]] = None,
        recency_days: Optional[int] = None,
    ) -> SearchResult:
        safe_limit = max(1, min(max_results, 20))
        search_query = _apply_domain_filter(query, domains)
        params: dict[str, str] = {
            "q": search_query,
            "format": "json",
            "language": "en",
        }
        time_range = _recency_to_time_range(recency_days)
        if time_range:
            params["time_range"] = time_range
        url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json", "User-Agent": "Termit/1.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            return SearchResult(
                query=query,
                hits=[
                    SearchHit(
                        title="SearXNG search failed",
                        url="",
                        snippet=str(exc),
                    )
                ],
                provider="searxng_error",
                citations=[],
            )

        hits = _parse_searxng_hits(raw, safe_limit, domains=domains)
        citations = [hit.url for hit in hits if hit.url]
        return SearchResult(query=query, hits=hits, provider=self.provider_label, citations=citations)


class HttpSearchProvider:
    """Structured search via configurable HTTP endpoint."""

    def __init__(self, api_url: str, api_key: str = "", *, provider_label: str = "http") -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key.strip()
        self.provider_label = provider_label

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        domains: Optional[list[str]] = None,
        recency_days: Optional[int] = None,
    ) -> SearchResult:
        payload: dict[str, object] = {
            "query": query,
            "max_results": max(1, min(max_results, 20)),
        }
        if domains:
            payload["search_domain_filter"] = domains
        if recency_days is not None and recency_days > 0:
            payload["search_recency_filter"] = f"{recency_days}d"
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(  # noqa: S310
            url=self.api_url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            return SearchResult(
                query=query,
                hits=[
                    SearchHit(
                        title="Search failed",
                        url="",
                        snippet=str(exc),
                    )
                ],
                provider="http_error",
                citations=[],
            )

        hits = _parse_generic_search_hits(raw, max_results)
        citations = [hit.url for hit in hits if hit.url]
        return SearchResult(query=query, hits=hits, provider=self.provider_label, citations=citations)


class PerplexitySearchProvider(HttpSearchProvider):
    """Optional legacy preset for Perplexity Search API."""

    def __init__(self, api_key: str, api_url: str = PERPLEXITY_SEARCH_URL) -> None:
        super().__init__(api_url=api_url, api_key=api_key, provider_label="perplexity")


class ExaSearchProvider(HttpSearchProvider):
    """Exa neural search API (https://exa.ai)."""

    def __init__(self, api_key: str, api_url: str = EXA_SEARCH_URL) -> None:
        super().__init__(api_url=api_url, api_key=api_key, provider_label="exa")


def _apply_domain_filter(query: str, domains: Optional[list[str]]) -> str:
    cleaned = query.strip()
    if not domains:
        return cleaned
    site_filters = " OR ".join(f"site:{domain.strip()}" for domain in domains if domain.strip())
    if not site_filters:
        return cleaned
    return f"{cleaned} ({site_filters})"


def _recency_to_time_range(recency_days: Optional[int]) -> Optional[str]:
    if recency_days is None or recency_days <= 0:
        return None
    if recency_days <= 1:
        return "day"
    if recency_days <= 7:
        return "week"
    if recency_days <= 31:
        return "month"
    return "year"


def _parse_searxng_hits(
    raw: object,
    max_results: int,
    *,
    domains: Optional[list[str]] = None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    results = raw.get("results") if isinstance(raw, dict) else None
    if not isinstance(results, list):
        return hits
    allowed_domains = [domain.strip().lower() for domain in (domains or []) if domain.strip()]
    for item in results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if allowed_domains and not _url_matches_domains(url, allowed_domains):
            continue
        hits.append(
            SearchHit(
                title=str(item.get("title") or "result"),
                url=url,
                snippet=str(item.get("content") or item.get("snippet") or "")[:500],
                score=float(item.get("score") or item.get("priority") or 1.0),
            )
        )
        if len(hits) >= max_results:
            break
    return hits


def _url_matches_domains(url: str, domains: list[str]) -> bool:
    lowered = url.lower()
    return any(domain in lowered for domain in domains)


def _parse_generic_search_hits(raw: object, max_results: int) -> list[SearchHit]:
    hits: list[SearchHit] = []
    results = raw.get("results") if isinstance(raw, dict) else None
    if isinstance(results, list):
        for item in results[:max_results]:
            if not isinstance(item, dict):
                continue
            hits.append(
                SearchHit(
                    title=str(item.get("title") or item.get("name") or "result"),
                    url=str(item.get("url") or ""),
                    snippet=str(item.get("snippet") or item.get("content") or "")[:500],
                )
            )
    return hits


def _maybe_cache_search(inner: SearchProvider, cache_ttl_seconds: int) -> SearchProvider:
    if cache_ttl_seconds > 0 and not isinstance(inner, StubSearchProvider):
        return CachedSearchProvider(inner, cache_ttl_seconds)
    return inner


def build_search_provider(
    api_url: str,
    api_key: str = "",
    *,
    provider: str = "searxng",
    cache_ttl_seconds: int = 0,
) -> SearchProvider:
    provider_name = (provider or "searxng").strip().lower()
    url = api_url.strip()
    key = api_key.strip()

    if provider_name == "stub":
        return StubSearchProvider()

    inner: SearchProvider

    if provider_name == "perplexity":
        if key or url:
            inner = PerplexitySearchProvider(api_key=key, api_url=url or PERPLEXITY_SEARCH_URL)
        else:
            return StubSearchProvider()
    elif provider_name == "exa":
        if key:
            inner = ExaSearchProvider(api_key=key, api_url=url or EXA_SEARCH_URL)
        else:
            return StubSearchProvider()
    elif provider_name == "searxng":
        inner = SearxngSearchProvider(url or DEFAULT_SEARXNG_URL, key)
    elif provider_name == "http":
        if url:
            inner = HttpSearchProvider(api_url=url, api_key=key, provider_label="http")
        else:
            return StubSearchProvider()
    elif provider_name == "auto":
        if key and not url:
            inner = PerplexitySearchProvider(api_key=key)
        elif url:
            if "perplexity.ai" in url:
                inner = PerplexitySearchProvider(api_key=key, api_url=url)
            elif "exa.ai" in url:
                inner = ExaSearchProvider(api_key=key, api_url=url)
            elif _looks_like_searxng_url(url):
                inner = SearxngSearchProvider(url, key)
            else:
                inner = HttpSearchProvider(api_url=url, api_key=key, provider_label="http")
        else:
            inner = SearxngSearchProvider(DEFAULT_SEARXNG_URL, key)
    elif url:
        if _looks_like_searxng_url(url):
            inner = SearxngSearchProvider(url, key)
        else:
            inner = HttpSearchProvider(api_url=url, api_key=key, provider_label=provider_name)
    else:
        return StubSearchProvider()

    return _maybe_cache_search(inner, cache_ttl_seconds)


def _looks_like_searxng_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.endswith("/search") or "searx" in lowered or ":8888" in lowered
