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


def probe_cloud_benchmark() -> dict[str, object]:
    from app.core.config import get_settings

    if os.getenv("TERMIT_CLOUD_BENCHMARK_DEV_READY", "").lower() in {"1", "true", "yes"}:
        settings = get_settings()
        return {
            "ready": True,
            "reason": "dev_stub",
            "dev_only": True,
            "reference_model": settings.eval_benchmark_reference_model,
            "hint": "Cloud benchmark dev stub (TERMIT_CLOUD_BENCHMARK_DEV_READY).",
        }

    settings = get_settings()
    openai_compat_key = os.getenv("OPENAI_COMPAT_API_KEY", settings.openai_compat_api_key or "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", settings.openai_api_key or "").strip()
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", settings.openai_compat_base_url or "").strip()
    reference = settings.eval_benchmark_reference_model

    has_key = bool(openai_compat_key or openai_key)
    if not has_key:
        return {
            "ready": False,
            "reason": "missing_api_key",
            "reference_model": reference,
            "hint": "Set OPENAI_COMPAT_API_KEY or OPENAI_API_KEY for cloud benchmark.",
        }

    reachable = False
    probe_url = ""
    if base_url:
        probe_url = base_url.rstrip("/") + "/models"
        try:
            request = urllib.request.Request(
                probe_url,
                headers={"Authorization": f"Bearer {openai_compat_key or openai_key}"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
                reachable = 200 <= int(response.status) < 300
        except (urllib.error.URLError, TimeoutError, ValueError):
            reachable = False

    return {
        "ready": has_key,
        "reason": "ok" if has_key else "missing_api_key",
        "reference_model": reference,
        "openai_compat_base_url": base_url,
        "api_reachable": reachable,
        "probe_url": probe_url or None,
    }


def main() -> int:
    print(json.dumps(probe_cloud_benchmark(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
