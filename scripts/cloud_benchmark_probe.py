#!/usr/bin/env python3
"""Probe whether cloud/model benchmark can run (API keys + optional reachability)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _probe_models_list(base_url: str, api_key: str) -> tuple[bool, list[str]]:
    """Проверяет /models и возвращает id доступных моделей (если API отвечает)."""
    probe_url = base_url.rstrip("/") + "/models"
    try:
        request = urllib.request.Request(
            probe_url,
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
            if not (200 <= int(response.status) < 300):
                return False, []
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return False, []

    ids: list[str] = []
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
    return True, ids


def probe_cloud_benchmark() -> dict[str, object]:
    from app.core.config import get_settings
    from app.core.frontier_models import (
        frontier_fallback_chain,
        resolve_benchmark_reference_model,
    )

    if os.getenv("TERMIT_CLOUD_BENCHMARK_DEV_READY", "").lower() in {"1", "true", "yes"}:
        settings = get_settings()
        reference = resolve_benchmark_reference_model(settings)
        return {
            "ready": True,
            "reason": "dev_stub",
            "dev_only": True,
            "reference_model": reference,
            "frontier_chain": frontier_fallback_chain(settings),
            "hint": "Cloud benchmark dev stub (TERMIT_CLOUD_BENCHMARK_DEV_READY).",
        }

    settings = get_settings()
    openai_compat_key = os.getenv("OPENAI_COMPAT_API_KEY", settings.openai_compat_api_key or "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", settings.openai_api_key or "").strip()
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", settings.openai_compat_base_url or "").strip()
    reference = resolve_benchmark_reference_model(settings)
    chain = frontier_fallback_chain(settings)
    api_key = openai_compat_key or openai_key

    has_key = bool(api_key)
    if not has_key:
        return {
            "ready": False,
            "reason": "missing_api_key",
            "reference_model": reference,
            "frontier_chain": chain,
            "hint": "Задайте OPENAI_COMPAT_API_KEY или OPENAI_API_KEY для cloud benchmark.",
        }

    reachable = False
    probe_url = ""
    listed_models: list[str] = []
    if base_url:
        reachable, listed_models = _probe_models_list(base_url, api_key)
        probe_url = base_url.rstrip("/") + "/models"

    reference_available = False
    if listed_models:
        bare_ref = reference.split(":", 1)[-1].strip().lower()
        reference_available = any(
            bare_ref in model_id.lower() or model_id.lower() in bare_ref
            for model_id in listed_models
        )

    chain_available: list[str] = []
    if listed_models:
        for model_id in chain:
            bare = model_id.split(":", 1)[-1].strip().lower()
            if any(bare in listed_id.lower() or listed_id.lower() in bare for listed_id in listed_models):
                chain_available.append(model_id)

    return {
        "ready": has_key,
        "reason": "ok" if has_key else "missing_api_key",
        "reference_model": reference,
        "frontier_chain": chain,
        "frontier_chain_available": chain_available,
        "reference_model_listed": reference_available if listed_models else None,
        "openai_compat_base_url": base_url,
        "api_reachable": reachable,
        "probe_url": probe_url or None,
        "models_listed_count": len(listed_models),
        "hint": (
            "V4 reference не найден в /models — задайте TERMIT_FRONTIER_FALLBACK_CHAIN "
            "или TERMIT_EVAL_BENCHMARK_REFERENCE_MODEL=openai_compat:deepseek-ai/DeepSeek-V3"
            if listed_models and not reference_available
            else None
        ),
    }


def main() -> int:
    print(json.dumps(probe_cloud_benchmark(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
