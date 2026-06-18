#!/usr/bin/env python3
"""Verify shadow traffic and regression gate flags on finetune training dashboard."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _get_dashboard(base_url: str, api_key: str, timeout: int) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/finetune/training/dashboard?limit=3",
        headers=headers,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _evaluate(dashboard: dict[str, object], *, min_shadow: float) -> tuple[bool, dict[str, object]]:
    shadow_percent = float(dashboard.get("shadow_traffic_percent", 0.0) or 0.0)
    regression_enabled = bool(dashboard.get("regression_gate_enabled", False))
    summary = {
        "shadow_traffic_percent": shadow_percent,
        "regression_gate_enabled": regression_enabled,
        "required_min_shadow_percent": min_shadow,
        "gate_passed": shadow_percent + 1e-9 >= min_shadow and regression_enabled,
    }
    return bool(summary["gate_passed"]), summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow traffic gate for weekly closed loop")
    parser.add_argument("--base-url", default=os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--api-key", default=os.getenv("TERMIT_API_KEY", ""))
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument(
        "--min-shadow-percent",
        type=float,
        default=float(os.getenv("TERMIT_FINETUNE_SHADOW_TRAFFIC_PERCENT", "10")),
    )
    args = parser.parse_args(argv)

    min_shadow = max(0.0, min(100.0, float(args.min_shadow_percent)))

    try:
        dashboard = _get_dashboard(args.base_url, args.api_key.strip(), max(3, args.timeout))
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Shadow traffic gate failed: dashboard unreachable ({exc}).", file=sys.stderr)
        return 1

    ok, summary = _evaluate(dashboard, min_shadow=min_shadow)
    print(json.dumps(summary, indent=2))

    if not ok:
        if not summary["regression_gate_enabled"]:
            print("Shadow traffic gate failed: regression_gate_enabled=false.", file=sys.stderr)
        else:
            print(
                f"Shadow traffic gate failed: shadow_traffic_percent={summary['shadow_traffic_percent']} "
                f"< required {min_shadow}.",
                file=sys.stderr,
            )
        return 1

    print(
        f"Shadow traffic gate passed: shadow={summary['shadow_traffic_percent']}%, "
        "regression_gate_enabled=true."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
