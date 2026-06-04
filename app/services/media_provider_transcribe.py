"""OpenAI Whisper transcription + stub SRT for Media Studio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx


class MediaTranscribeError(Exception):
    pass


@dataclass(frozen=True)
class TranscribeResult:
    srt_text: str
    provider: str
    cost_usd: float
    language: str


class OpenAITranscribeProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_cost_usd: float = 0.006,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._default_cost = default_cost_usd

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def transcribe(
        self,
        *,
        media_path: Path,
        language: str | None = None,
    ) -> TranscribeResult:
        if not media_path.is_file():
            raise MediaTranscribeError(f"Media file not found: {media_path}")
        lang = (language or "ru").strip()
        if not self._api_key:
            stub = (
                "1\n"
                "00:00:00,000 --> 00:00:02,000\n"
                "[stub transcription — set OPENAI_API_KEY for Whisper]\n"
            )
            return TranscribeResult(
                srt_text=stub,
                provider="stub",
                cost_usd=0.0,
                language=lang,
            )
        with httpx.Client(timeout=180.0) as client:
            with media_path.open("rb") as handle:
                files = {"file": (media_path.name, handle, "application/octet-stream")}
                data: dict[str, str] = {"model": "whisper-1", "response_format": "srt"}
                if language:
                    data["language"] = lang.split("-")[0]
                response = client.post(
                    f"{self._base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=data,
                    files=files,
                )
        if response.status_code >= 400:
            raise MediaTranscribeError(
                f"Whisper error {response.status_code}: {response.text[:500]}"
            )
        return TranscribeResult(
            srt_text=response.text,
            provider="openai",
            cost_usd=self._default_cost,
            language=lang,
        )
