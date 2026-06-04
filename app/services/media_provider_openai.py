"""OpenAI Images API provider."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx


class MediaProviderError(Exception):
    pass


@dataclass(frozen=True)
class ImageGenerationResult:
    bytes_data: bytes
    mime: str
    provider: str
    model: str
    cost_usd: float
    revised_prompt: Optional[str] = None


class OpenAIImageProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        image_model: str = "dall-e-3",
        default_cost_usd: float = 0.08,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._image_model = image_model
        self._default_cost = default_cost_usd

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        quality: str = "standard",
    ) -> ImageGenerationResult:
        if not self._api_key:
            raise MediaProviderError("OPENAI_API_KEY is not configured.")
        size = _map_size(width, height)
        payload = {
            "model": self._image_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }
        if self._image_model.startswith("dall-e"):
            payload["quality"] = quality
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base_url}/images/generations",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            raise MediaProviderError(f"OpenAI Images error {response.status_code}: {response.text[:500]}")
        data = response.json()
        items = data.get("data", [])
        if not items:
            raise MediaProviderError("OpenAI Images returned empty data.")
        item = items[0]
        revised = item.get("revised_prompt")
        b64 = item.get("b64_json")
        if not b64:
            url = item.get("url")
            if not url:
                raise MediaProviderError("OpenAI Images response missing b64_json and url.")
            with httpx.Client(timeout=60.0) as client:
                img_resp = client.get(url)
            if img_resp.status_code >= 400:
                raise MediaProviderError(f"Failed to download image url: {img_resp.status_code}")
            raw = img_resp.content
        else:
            raw = base64.b64decode(b64)
        return ImageGenerationResult(
            bytes_data=raw,
            mime="image/png",
            provider="openai",
            model=self._image_model,
            cost_usd=self._default_cost,
            revised_prompt=str(revised) if revised else None,
        )


def _map_size(width: int, height: int) -> str:
    w, h = max(width, 1), max(height, 1)
    ratio = w / h
    if ratio > 1.2:
        return "1792x1024" if max(w, h) >= 1024 else "1024x576"
    if ratio < 0.8:
        return "1024x1792" if max(w, h) >= 1024 else "576x1024"
    return "1024x1024"
