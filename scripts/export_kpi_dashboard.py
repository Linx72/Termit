#!/usr/bin/env python3
"""Export a combined KPI dashboard JSON bundle from Termit metrics API."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch_json(url: str, method: str = "GET", api_key: str = "") -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(url=url, method=method, headers=headers)
    with urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Termit KPI dashboard bundle.")
    parser.add_argument("--base-url", default="http://localhost:8765")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--capture", action="store_true", help="Capture snapshot before export")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    query = urlencode({"days": args.days, "limit": args.limit})

    try:
        if args.capture:
            fetch_json(f"{base}/api/metrics/snapshot", method="POST", api_key=args.api_key)

        bundle = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "period_days": args.days,
            "current": fetch_json(f"{base}/api/metrics", api_key=args.api_key),
            "trend": fetch_json(f"{base}/api/metrics/trend?{query}", api_key=args.api_key),
            "daily_report": fetch_json(f"{base}/api/metrics/daily-report?{query}", api_key=args.api_key),
            "executive_summary": fetch_json(
                f"{base}/api/metrics/executive-summary?{query}",
                api_key=args.api_key,
            ),
            "slack_summary": fetch_json(
                f"{base}/api/metrics/executive-summary/slack?{query}",
                api_key=args.api_key,
            ),
            "beta_metrics": fetch_json(f"{base}/api/ops/beta-metrics", api_key=args.api_key),
            "feedback_summary": fetch_json(f"{base}/api/feedback/summary", api_key=args.api_key),
            "kpi_gates": fetch_json(f"{base}/api/desktop/kpi-gates", api_key=args.api_key),
        }
    except HTTPError as exc:
        print(f"HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 2

    encoded = json.dumps(bundle, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(encoded)
    else:
        from pathlib import Path

        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
