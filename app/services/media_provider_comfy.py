"""ComfyUI HTTP API — локальная генерация SDXL для Media Studio."""

from __future__ import annotations

import json
import random
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

import httpx

from app.services.media_provider_openai import ImageGenerationResult, MediaProviderError

# Узлы workflow `data/media/workflows/sdxl_t2i_api.json`
_NODE_KSAMPLER = "3"
_NODE_CHECKPOINT = "4"
_NODE_LATENT = "5"
_NODE_POSITIVE = "6"
_NODE_NEGATIVE = "7"
_NODE_SAVE_IMAGE = "9"

_DEFAULT_NEGATIVE = "text, watermark, blurry, low quality, distorted"


def _round_sdxl_dim(value: int) -> int:
    """SDXL требует размеры кратные 8; ограничиваем разумным диапазоном."""
    clamped = max(512, min(2048, value))
    return max(512, (clamped // 8) * 8)


def load_workflow_template(path: Path) -> dict[str, Any]:
    """Загрузить workflow JSON для ComfyUI API."""
    if not path.is_file():
        raise MediaProviderError(f"ComfyUI workflow не найден: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MediaProviderError(f"Некорректный workflow JSON: {path}")
    return raw


def build_sdxl_workflow(
    template: dict[str, Any],
    *,
    prompt: str,
    width: int,
    height: int,
    checkpoint: str,
    negative_prompt: str = _DEFAULT_NEGATIVE,
    seed: Optional[int] = None,
    steps: int = 20,
    cfg: float = 7.0,
) -> dict[str, Any]:
    """Подставить prompt/size/checkpoint в шаблон workflow."""
    workflow = deepcopy(template)
    chosen_seed = seed if seed is not None else random.randint(0, 2**32 - 1)
    w, h = _round_sdxl_dim(width), _round_sdxl_dim(height)

    workflow[_NODE_CHECKPOINT]["inputs"]["ckpt_name"] = checkpoint
    workflow[_NODE_LATENT]["inputs"]["width"] = w
    workflow[_NODE_LATENT]["inputs"]["height"] = h
    workflow[_NODE_POSITIVE]["inputs"]["text"] = prompt
    workflow[_NODE_NEGATIVE]["inputs"]["text"] = negative_prompt
    workflow[_NODE_KSAMPLER]["inputs"]["seed"] = chosen_seed
    workflow[_NODE_KSAMPLER]["inputs"]["steps"] = steps
    workflow[_NODE_KSAMPLER]["inputs"]["cfg"] = cfg
    return workflow


class ComfyImageProvider:
    """Клиент ComfyUI `/prompt` + `/history` + `/view` для SDXL text2image."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8188",
        workflow_path: str = "./data/media/workflows/sdxl_t2i_api.json",
        checkpoint: str = "sd_xl_base_1.0.safetensors",
        timeout_sec: float = 180.0,
        poll_interval_sec: float = 1.0,
        default_cost_usd: float = 0.0,
        negative_prompt: str = _DEFAULT_NEGATIVE,
    ) -> None:
        self._base_url = base_url.strip().rstrip("/")
        self._workflow_path = Path(workflow_path)
        self._checkpoint = checkpoint.strip() or "sd_xl_base_1.0.safetensors"
        self._timeout_sec = max(30.0, timeout_sec)
        self._poll_interval_sec = max(0.25, poll_interval_sec)
        self._default_cost = default_cost_usd
        self._negative_prompt = negative_prompt.strip() or _DEFAULT_NEGATIVE

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def available(self) -> bool:
        return self.health_check()

    def health_check(self, timeout_sec: float = 3.0) -> bool:
        """Проверить, что ComfyUI отвечает на /system_stats."""
        if not self._base_url:
            return False
        try:
            with httpx.Client(timeout=timeout_sec) as client:
                response = client.get(f"{self._base_url}/system_stats")
            return response.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: Optional[int] = None,
    ) -> ImageGenerationResult:
        if not self._base_url:
            raise MediaProviderError("TERMIT_MEDIA_COMFY_URL не задан.")
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise MediaProviderError("generate_image requires non-empty prompt.")

        template = load_workflow_template(self._workflow_path)
        workflow = build_sdxl_workflow(
            template,
            prompt=clean_prompt,
            width=width,
            height=height,
            checkpoint=self._checkpoint,
            negative_prompt=self._negative_prompt,
            seed=seed,
        )
        client_id = uuid.uuid4().hex
        payload = {"prompt": workflow, "client_id": client_id}

        with httpx.Client(timeout=self._timeout_sec) as client:
            response = client.post(f"{self._base_url}/prompt", json=payload)
            if response.status_code >= 400:
                raise MediaProviderError(
                    f"ComfyUI /prompt error {response.status_code}: {response.text[:500]}"
                )
            prompt_id = response.json().get("prompt_id")
            if not prompt_id:
                raise MediaProviderError("ComfyUI /prompt не вернул prompt_id.")

            image_meta = self._wait_for_output(client, str(prompt_id))
            raw = self._download_image(client, image_meta)

        return ImageGenerationResult(
            bytes_data=raw,
            mime="image/png",
            provider="comfy",
            model=self._checkpoint,
            cost_usd=self._default_cost,
            revised_prompt=None,
        )

    def _wait_for_output(self, client: httpx.Client, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._timeout_sec
        last_error = ""
        while time.monotonic() < deadline:
            response = client.get(f"{self._base_url}/history/{prompt_id}")
            if response.status_code >= 400:
                raise MediaProviderError(
                    f"ComfyUI /history error {response.status_code}: {response.text[:300]}"
                )
            history = response.json()
            entry = history.get(prompt_id) if isinstance(history, dict) else None
            if isinstance(entry, dict):
                outputs = entry.get("outputs") or {}
                save_out = outputs.get(_NODE_SAVE_IMAGE) or {}
                images = save_out.get("images") or []
                if images:
                    first = images[0]
                    if isinstance(first, dict) and first.get("filename"):
                        return first
                status = entry.get("status") or {}
                if isinstance(status, dict) and status.get("status_str") == "error":
                    messages = status.get("messages") or []
                    last_error = str(messages)[:500]
                    break
            time.sleep(self._poll_interval_sec)
        hint = f" ({last_error})" if last_error else ""
        raise MediaProviderError(
            f"ComfyUI timeout {self._timeout_sec:.0f}s — нет PNG в history/{prompt_id}{hint}"
        )

    def _download_image(self, client: httpx.Client, meta: dict[str, Any]) -> bytes:
        filename = str(meta.get("filename") or "")
        if not filename:
            raise MediaProviderError("ComfyUI output без filename.")
        params = {
            "filename": filename,
            "subfolder": str(meta.get("subfolder") or ""),
            "type": str(meta.get("type") or "output"),
        }
        response = client.get(f"{self._base_url}/view", params=params)
        if response.status_code >= 400:
            raise MediaProviderError(f"ComfyUI /view error {response.status_code}")
        if not response.content:
            raise MediaProviderError("ComfyUI /view вернул пустое тело.")
        return response.content
