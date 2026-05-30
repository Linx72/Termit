#!/usr/bin/env python3
"""Export Termit KPI metrics snapshot via HTTP API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Termit KPI snapshot JSON.")
    parser.add_argument("--base-url", default="http://localhost:8765", help="Termit base URL")
    parser.add_argument(
        "--api-key",
        default="",
        help="API key when TERMIT_AUTH_ENABLED=true",
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="POST /api/metrics/snapshot before exporting current metrics",
    )
    parser.add_argument("--output", default="-", help="Output file path or '-' for stdout")
    args = parser.parse_args()

    headers = {"Accept": "application/json"}
    if args.api_key:
        headers["X-API-Key"] = args.api_key

    if args.capture:
        capture_request = urllib.request.Request(
            f"{args.base_url.rstrip('/')}/api/metrics/snapshot",
            method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(capture_request, timeout=30) as response:
            capture_request.read()
            if response.status != 200:
                print(f"Unexpected capture status: {response.status}", file=sys.stderr)
                return 1

    metrics_request = urllib.request.Request(
        f"{args.base_url.rstrip('/')}/api/metrics",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(metrics_request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"Failed to fetch metrics: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(encoded)
    else:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
