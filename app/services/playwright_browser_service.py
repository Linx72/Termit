from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


class PlaywrightUnavailableError(Exception):
    pass


@dataclass
class BrowserSession:
    url: str = ""
    title: str = ""
    text_excerpt: str = ""
    html: str = ""


@dataclass
class PlaywrightBrowserService:
    """Optional headless browser for JS-heavy pages. Requires: pip install playwright && playwright install chromium."""

    _session: BrowserSession = field(default_factory=BrowserSession)
    _playwright: object | None = field(default=None, repr=False)
    _browser: object | None = field(default=None, repr=False)
    _page: object | None = field(default=None, repr=False)

    def available(self) -> bool:
        try:
            import playwright  # noqa: F401

            return True
        except ImportError:
            return False

    def navigate(self, url: str, *, timeout_seconds: int = 30) -> dict[str, object]:
        page = self._ensure_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
        html = page.content()
        title = page.title()
        text = _strip_html(html)
        self._session = BrowserSession(
            url=str(page.url),
            title=title,
            text_excerpt=text[:4000],
            html=html,
        )
        return {
            "url": self._session.url,
            "title": title,
            "text_excerpt": self._session.text_excerpt[:1200],
            "backend": "playwright",
        }

    def snapshot(self) -> dict[str, object]:
        if not self._session.url:
            raise PlaywrightUnavailableError("No active browser session. Call browser_navigate first.")
        return {
            "url": self._session.url,
            "title": self._session.title,
            "text_excerpt": self._session.text_excerpt[:2000],
            "backend": "playwright",
        }

    def click(self, selector: str, *, confirmed: bool = False) -> dict[str, object]:
        if not confirmed:
            return {
                "executed": False,
                "detail": "browser_click requires confirmed=true (human approval).",
            }
        page = self._ensure_page()
        page.click(selector, timeout=15000)
        html = page.content()
        self._session.html = html
        self._session.text_excerpt = _strip_html(html)[:4000]
        self._session.title = page.title()
        self._session.url = str(page.url)
        return {
            "executed": True,
            "url": self._session.url,
            "title": self._session.title,
            "backend": "playwright",
        }

    def fetch_as_http(self, url: str, timeout_seconds: int) -> tuple[int, str, str]:
        """Playwright-backed fetch compatible with BrowserWorkflowService."""
        result = self.navigate(url, timeout_seconds=timeout_seconds)
        status = 200
        return status, self._session.html, str(result.get("url", url))

    def close(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:  # noqa: BLE001
                pass
            self._page = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:  # noqa: BLE001
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # noqa: BLE001
                pass
            self._playwright = None

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlaywrightUnavailableError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            ) from exc
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        return self._page


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
