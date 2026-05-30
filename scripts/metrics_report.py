#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _request_json(url: str, method: str = "GET") -> dict:
    request = Request(url=url, method=method)
    with urlopen(request, timeout=20) as response:  # noqa: S310
        body = response.read().decode("utf-8")
        return json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and report Termit KPI snapshots.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8765",
        help="Termit API base URL",
    )
    parser.add_argument(
        "--mode",
        choices=["snapshot", "daily-report", "executive-summary", "slack-summary", "slack-payload"],
        default="snapshot",
        help="Run snapshot capture or print KPI reports",
    )
    parser.add_argument("--days", type=int, default=7, help="Period for daily report")
    parser.add_argument("--limit", type=int, default=200, help="Trend point limit")
    args = parser.parse_args()

    try:
        if args.mode == "snapshot":
            payload = _request_json(f"{args.base_url}/api/metrics/snapshot", method="POST")
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0

        endpoint = "/api/metrics/daily-report"
        if args.mode == "executive-summary":
            endpoint = "/api/metrics/executive-summary"
        elif args.mode == "slack-summary":
            endpoint = "/api/metrics/executive-summary/slack"
        elif args.mode == "slack-payload":
            endpoint = "/api/metrics/executive-summary/slack/payload"
        payload = _request_json(
            f"{args.base_url}{endpoint}?days={args.days}&limit={args.limit}",
            method="GET",
        )
        if args.mode == "slack-summary":
            print(payload.get("text", ""))
        elif args.mode == "slack-payload":
            print(json.dumps(payload.get("payload", {}), ensure_ascii=True, indent=2))
        else:
            print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0
    except HTTPError as exc:
        print(f"HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON response: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
