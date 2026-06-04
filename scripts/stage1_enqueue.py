#!/usr/bin/env python3
"""Enqueue a Stage1 finetune pipeline run via Termit HTTP API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def build_payload(
    *,
    name: str,
    base_model: str,
    min_samples: int,
    run_eval_baseline: bool,
    eval_limit: int,
    auto_register_adapter: bool,
) -> dict[str, object]:
    return {
        "name": name,
        "base_model": base_model,
        "min_samples": min_samples,
        "run_eval_baseline": run_eval_baseline,
        "eval_limit": eval_limit,
        "auto_register_adapter": auto_register_adapter,
    }


def check_health(base_url: str, api_key: Optional[str], timeout: float) -> None:
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(url=f"{base_url.rstrip('/')}/health", headers=headers, method="GET")
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError(f"Health check failed with status {response.status}")


def enqueue_stage1_run(
    *,
    base_url: str,
    api_key: Optional[str],
    payload: dict[str, object],
    timeout: float,
) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = Request(
        url=f"{base_url.rstrip('/')}/api/finetune/pipeline/stage1-runs",
        data=body,
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read().decode("utf-8")
        return json.loads(raw)


def resolve_settings_from_env() -> dict[str, object]:
    return {
        "base_url": os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765"),
        "api_key": os.getenv("TERMIT_API_KEY") or None,
        "name": os.getenv("TERMIT_STAGE1_NAME", "weekly-stage1"),
        "base_model": os.getenv(
            "TERMIT_STAGE1_BASE_MODEL",
            os.getenv("TERMIT_TEACHER_MODEL", "ollama:deepseek-coder"),
        ),
        "min_samples": int(os.getenv("TERMIT_STAGE1_MIN_SAMPLES", "10")),
        "run_eval_baseline": os.getenv("TERMIT_STAGE1_RUN_EVAL_BASELINE", "true").lower()
        in {"1", "true", "yes"},
        "eval_limit": int(os.getenv("TERMIT_STAGE1_EVAL_LIMIT", "24")),
        "auto_register_adapter": os.getenv("TERMIT_STAGE1_AUTO_REGISTER_ADAPTER", "false").lower()
        in {"1", "true", "yes"},
        "timeout": float(os.getenv("TERMIT_STAGE1_HTTP_TIMEOUT", "30")),
        "require_health": os.getenv("TERMIT_STAGE1_REQUIRE_HEALTH", "true").lower()
        in {"1", "true", "yes"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Enqueue Termit Stage1 finetune pipeline run")
    parser.add_argument("--base-url", default=None, help="Termit API base URL")
    parser.add_argument("--api-key", default=None, help="API key when TERMIT_AUTH_ENABLED=true")
    parser.add_argument("--name", default=None, help="Pipeline run name")
    parser.add_argument("--base-model", default=None, help="Base model id")
    parser.add_argument("--min-samples", type=int, default=None)
    parser.add_argument("--eval-limit", type=int, default=None)
    parser.add_argument("--no-eval-baseline", action="store_true")
    parser.add_argument("--auto-register-adapter", action="store_true")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--skip-health-check", action="store_true")
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Load defaults from TERMIT_* environment variables",
    )
    args = parser.parse_args()

    env_settings = resolve_settings_from_env() if args.from_env or not args.base_url else {}
    base_url = args.base_url or env_settings.get("base_url") or "http://127.0.0.1:8765"
    api_key = args.api_key if args.api_key is not None else env_settings.get("api_key")
    name = args.name or env_settings.get("name") or "weekly-stage1"
    base_model = (
        args.base_model
        or env_settings.get("base_model")
        or os.getenv("TERMIT_TEACHER_MODEL", "ollama:deepseek-coder")
    )
    min_samples = args.min_samples if args.min_samples is not None else int(env_settings.get("min_samples", 10))
    eval_limit = args.eval_limit if args.eval_limit is not None else int(env_settings.get("eval_limit", 24))
    timeout = args.timeout if args.timeout is not None else float(env_settings.get("timeout", 30))
    require_health = not args.skip_health_check and bool(env_settings.get("require_health", True))
    run_eval_baseline = not args.no_eval_baseline
    if args.from_env and "run_eval_baseline" in env_settings:
        run_eval_baseline = bool(env_settings["run_eval_baseline"])
    auto_register_adapter = args.auto_register_adapter or bool(env_settings.get("auto_register_adapter", False))

    payload = build_payload(
        name=str(name),
        base_model=str(base_model),
        min_samples=min_samples,
        run_eval_baseline=run_eval_baseline,
        eval_limit=eval_limit,
        auto_register_adapter=auto_register_adapter,
    )

    try:
        if require_health:
            check_health(str(base_url), api_key if isinstance(api_key, str) else None, timeout)
        result = enqueue_stage1_run(
            base_url=str(base_url),
            api_key=api_key if isinstance(api_key, str) else None,
            payload=payload,
            timeout=timeout,
        )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error {exc.code}: {detail}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
