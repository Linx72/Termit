#!/usr/bin/env python3
"""Bootstrap real beta actors на staging через POST /api/ops/beta/activity."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _post_activity(
    *,
    base_url: str,
    api_key: str,
    session_id: str,
    source: str,
) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    body = json.dumps({"session_id": session_id, "source": source}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/ops/beta/activity",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        raw = response.read().decode("utf-8")
        payload = json.loads(raw) if raw.strip() else {}
        return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap real beta cohort на staging")
    parser.add_argument(
        "--base-url",
        default=os.getenv("TERMIT_HOSTED_BASE_URL", os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8080")),
    )
    parser.add_argument("--api-key", default=os.getenv("TERMIT_API_KEY", ""))
    parser.add_argument("--actors", type=int, default=int(os.getenv("TERMIT_BETA_BOOTSTRAP_ACTORS", "5")))
    parser.add_argument("--prefix", default=os.getenv("TERMIT_BETA_BOOTSTRAP_PREFIX", "staging-real"))
    parser.add_argument("--source", default="bootstrap_staging")
    args = parser.parse_args()

    actors = max(1, args.actors)
    results: list[dict[str, object]] = []
    for index in range(actors):
        session_id = f"{args.prefix}-{index:02d}"
        try:
            payload = _post_activity(
                base_url=args.base_url,
                api_key=args.api_key,
                session_id=session_id,
                source=args.source,
            )
            results.append({"session_id": session_id, "ok": True, **payload})
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            results.append({"session_id": session_id, "ok": False, "error": str(exc)})

    ok_count = sum(1 for row in results if row.get("ok"))
    summary = {
        "base_url": args.base_url,
        "actors_requested": actors,
        "actors_ok": ok_count,
        "results": results,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if ok_count >= actors else 1


if __name__ == "__main__":
    raise SystemExit(main())
