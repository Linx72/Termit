#!/usr/bin/env python3
"""Fetch previous flaky-watch artifact baseline from GitHub Actions artifacts."""

from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FetchResult:
    status: str
    note: str
    baseline_found: bool


def _request_json(url: str, token: str) -> dict[str, Any]:
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(req, timeout=20) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Unexpected GitHub API payload type")
    return payload


def _download_file(url: str, token: str, target: Path) -> None:
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(req, timeout=30) as response:  # noqa: S310
        target.write_bytes(response.read())


def _classify_http_error(exc: HTTPError, *, context: str) -> FetchResult:
    text = f"{exc.code} {exc.reason}".lower()
    if exc.code == 403 and "rate limit" in text:
        return FetchResult("rate_limited", f"GitHub API rate limit during {context}.", False)
    if exc.code == 403:
        return FetchResult("forbidden", f"GitHub API forbidden during {context}.", False)
    return FetchResult("fetch_error", f"GitHub API error during {context}: {exc}.", False)


def fetch_baseline(
    *,
    token: str,
    repo: str,
    artifact_name: str,
    output_json_path: Path,
    output_zip_path: Path,
) -> FetchResult:
    if not token or not repo:
        return FetchResult("missing_credentials", "GITHUB_TOKEN or GITHUB_REPOSITORY is missing.", False)

    api_url = f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100"
    try:
        listing = _request_json(api_url, token)
    except HTTPError as exc:
        return _classify_http_error(exc, context="artifact listing")
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "http error 403" in msg and "rate limit" in msg:
            return FetchResult("rate_limited", "GitHub API rate limit while listing artifacts.", False)
        if "http error 403" in msg:
            return FetchResult("forbidden", "GitHub API forbidden while listing artifacts.", False)
        return FetchResult("fetch_error", f"Artifact listing error: {exc}", False)

    artifacts = [
        item
        for item in listing.get("artifacts", [])
        if isinstance(item, dict) and item.get("name") == artifact_name and not item.get("expired", False)
    ]
    artifacts.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    if not artifacts:
        return FetchResult("missing", "No previous flaky-watch artifact found.", False)

    download_url = str(artifacts[0].get("archive_download_url", "")).strip()
    if not download_url:
        return FetchResult("missing_payload", "Artifact found but archive URL is missing.", False)

    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _download_file(download_url, token, output_zip_path)
    except HTTPError as exc:
        return _classify_http_error(exc, context="artifact download")
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "http error 403" in msg and "rate limit" in msg:
            return FetchResult("rate_limited", "GitHub API rate limit during artifact download.", False)
        if "http error 403" in msg:
            return FetchResult("forbidden", "GitHub API forbidden during artifact download.", False)
        return FetchResult("download_error", f"Artifact download error: {exc}", False)

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip_path, "r") as archive:
        for name in archive.namelist():
            if name.endswith("flaky_watch_report.json"):
                output_json_path.write_bytes(archive.read(name))
                return FetchResult("available", "Baseline loaded from previous flaky-watch artifact.", True)
    return FetchResult("missing_payload", "Artifact found but flaky_watch_report.json is missing.", False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch previous flaky-watch baseline artifact.")
    parser.add_argument("--token", default="", help="GitHub token with actions read permissions.")
    parser.add_argument("--repo", default="", help="GitHub repository in owner/name format.")
    parser.add_argument("--artifact-name", default="flaky-watch-nightly", help="Artifact name to fetch.")
    parser.add_argument("--output-json", default="/tmp/flaky_watch_previous.json", help="Baseline JSON output path.")
    parser.add_argument("--output-zip", default="/tmp/flaky-watch-previous.zip", help="Downloaded archive path.")
    parser.add_argument("--status-path", default="/tmp/flaky_watch_baseline_status.txt", help="Status text file path.")
    parser.add_argument("--note-path", default="/tmp/flaky_watch_baseline_note.txt", help="Note text file path.")
    args = parser.parse_args()

    result = fetch_baseline(
        token=str(args.token or "").strip(),
        repo=str(args.repo or "").strip(),
        artifact_name=str(args.artifact_name or "flaky-watch-nightly"),
        output_json_path=Path(args.output_json),
        output_zip_path=Path(args.output_zip),
    )
    Path(args.status_path).write_text(result.status + "\n", encoding="utf-8")
    Path(args.note_path).write_text(result.note + "\n", encoding="utf-8")
    print(f"baseline_status={result.status}")
    print(f"baseline_note={result.note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
