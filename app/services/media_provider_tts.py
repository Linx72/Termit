"""OpenAI TTS + stub fallback for Media Studio."""

from __future__ import annotations

import struct
import wave
from dataclasses import dataclass
from pathlib import Path

import httpx


class MediaTtsError(Exception):
    pass


@dataclass(frozen=True)
class TtsResult:
    bytes_data: bytes
    mime: str
    provider: str
    cost_usd: float
    voice: str


def write_stub_wav(path: Path, *, duration_sec: float = 2.0, sample_rate: int = 44100) -> None:
    """Silent mono WAV — dev fallback when no API key."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(max(0.5, duration_sec) * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)


class OpenAITtsProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_voice: str = "alloy",
        default_cost_usd: float = 0.015,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._default_voice = default_voice
        self._default_cost = default_cost_usd

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def synthesize(
        self,
        *,
        text: str,
        voice: str | None = None,
        language: str = "ru",
    ) -> TtsResult:
        clean = text.strip()
        if not clean:
            raise MediaTtsError("tts_generate requires non-empty text.")
        chosen_voice = (voice or self._default_voice).strip() or self._default_voice
        if not self._api_key:
            path_bytes = _stub_wav_bytes(duration_sec=max(1.0, len(clean) / 20.0))
            return TtsResult(
                bytes_data=path_bytes,
                mime="audio/wav",
                provider="stub",
                cost_usd=0.0,
                voice=chosen_voice,
            )
        payload = {
            "model": "tts-1",
            "input": clean,
            "voice": chosen_voice,
            "response_format": "wav",
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base_url}/audio/speech",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            raise MediaTtsError(f"OpenAI TTS error {response.status_code}: {response.text[:500]}")
        return TtsResult(
            bytes_data=response.content,
            mime="audio/wav",
            provider="openai",
            cost_usd=self._default_cost,
            voice=chosen_voice,
        )


def _stub_wav_bytes(*, duration_sec: float, sample_rate: int = 44100) -> bytes:
    import io

    buffer = io.BytesIO()
    frames = int(max(0.5, duration_sec) * sample_rate)
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()
