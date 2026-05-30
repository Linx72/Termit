#!/usr/bin/env python3
"""Run Termit incident drill via HTTP API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Termit incident drill.")
    parser.add_argument("--base-url", default="http://localhost:8765")
    parser.add_argument("--api-key", default="", help="Admin API key")
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    path = "/api/ops/readiness" if args.readiness_only else "/api/ops/incident-drill"
    method = "GET" if args.readiness_only else "POST"
    headers = {"Accept": "application/json"}
    if args.api_key:
        headers["X-API-Key"] = args.api_key

    request = urllib.request.Request(
        f"{args.base_url.rstrip('/')}{path}",
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(encoded)
    else:
        from pathlib import Path

        Path(args.output).write_text(encoded + "\n", encoding="utf-8")

    status = payload.get("status", "unknown")
    return 0 if status in {"ready", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
