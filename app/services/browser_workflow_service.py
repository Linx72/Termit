from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import urljoin

import httpx

from app.domain.schemas import (
    WebAutomationRequest,
    WebAutomationResponse,
    WebEvidence,
)


class WebWorkflowError(Exception):
    pass


class BrowserWorkflowService:
    def __init__(
        self,
        fetcher: Callable[[str, int], tuple[int, str, str]] | None = None,
        *,
        backend_label: str = "httpx",
    ) -> None:
        self._fetcher = fetcher or self._default_fetcher
        self.backend_label = backend_label

    def run(self, payload: WebAutomationRequest) -> WebAutomationResponse:
        if not payload.url.startswith(("http://", "https://")):
            raise WebWorkflowError("URL must start with http:// or https://")

        started = time.perf_counter()
        steps: list[str] = []
        executed_actions: list[str] = []
        reached_step_limit = False
        available_actions = ["navigate", "analyze_content", "collect_evidence", "finalize"]

        for action in available_actions:
            if len(steps) >= payload.max_steps:
                steps.append("Stopped due to max_steps limit (anti-loop protection).")
                reached_step_limit = True
                break
            if action in executed_actions:
                steps.append(f"Skipped duplicated action '{action}' (anti-loop protection).")
                continue
            executed_actions.append(action)
            steps.append(f"Action: {action}")

        try:
            status_code, body, final_url = self._fetcher(payload.url, payload.timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started) * 1000)
            return WebAutomationResponse(
                objective=payload.objective,
                success=False,
                blocker_detected=False,
                blocker_reason=f"Fetch failed: {exc}",
                steps=steps,
                duration_ms=duration_ms,
            )

        title = self._extract_title(body)
        links = self._extract_links(base_url=final_url, html=body, limit=payload.capture_links_limit)
        blocker_reason = self._detect_blocker(body, status_code)
        excerpt = body[:1200]

        duration_ms = int((time.perf_counter() - started) * 1000)
        evidence = WebEvidence(
            requested_url=payload.url,
            final_url=final_url,
            status_code=status_code,
            title=title,
            links=links,
            snapshot_excerpt=excerpt,
        )

        if blocker_reason is not None:
            steps.append("Blocker detected; stopping workflow and requiring user handoff.")
            return WebAutomationResponse(
                objective=payload.objective,
                success=False,
                blocker_detected=True,
                blocker_reason=blocker_reason,
                steps=steps,
                evidence=evidence,
                duration_ms=duration_ms,
            )

        if not reached_step_limit:
            steps.append(f"Workflow finished with collected evidence (backend={self.backend_label}).")
        return WebAutomationResponse(
            objective=payload.objective,
            success=True,
            blocker_detected=False,
            steps=steps,
            evidence=evidence,
            duration_ms=duration_ms,
        )

    def _default_fetcher(self, url: str, timeout_seconds: int) -> tuple[int, str, str]:
        with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
            response = client.get(url)
            return response.status_code, response.text, str(response.url)

    def _extract_title(self, html: str) -> str | None:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        return title or None

    def _extract_links(self, base_url: str, html: str, limit: int) -> list[str]:
        raw_links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        links: list[str] = []
        for raw in raw_links:
            if len(links) >= limit:
                break
            if raw.startswith("#") or raw.startswith("javascript:"):
                continue
            links.append(urljoin(base_url, raw))
        return links

    def _detect_blocker(self, html: str, status_code: int) -> str | None:
        lowered = html.lower()
        if status_code in {401, 403}:
            return f"Access denied with status code {status_code}."

        blocker_markers = {
            "captcha": "CAPTCHA challenge detected.",
            "verify you are human": "Human verification challenge detected.",
            "sign in": "Login required (sign in).",
            "log in": "Login required (log in).",
            "password": "Password challenge detected.",
            "access denied": "Page indicates access denied.",
        }
        for marker, reason in blocker_markers.items():
            if marker in lowered:
                return reason
        return None
