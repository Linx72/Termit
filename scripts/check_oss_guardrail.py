#!/usr/bin/env python3
"""Validate mandatory OSS License/IP guardrail artifacts."""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path


REQUIRED_MATRIX = Path("docs/OSS_REUSE_MATRIX.md")
ADR_DIR = Path("docs/adr")
ADR_GLOB = "ADR-OSS-*.md"

REQUIRED_HEADINGS = [
    "## 1. Context",
    "## 2. License & IP Analysis",
    "## 3. Architecture Boundary",
    "## 4. Security & Compliance",
    "## 5. KPI Hypothesis",
    "## 6. Decision",
    "## 7. Rollback & Exit Strategy",
]

REQUIRED_FIELDS = [
    "SPDX license:",
    "Decision:",
    "Integration mode:",
    "Source URL:",
    "Expiration / review date:",
]

REVIEW_DATE_RE = re.compile(r"Expiration / review date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")


def _validate_adr(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            errors.append(f"{path}: missing heading `{heading}`")
    for field in REQUIRED_FIELDS:
        if field not in text:
            errors.append(f"{path}: missing field `{field}`")
    match = REVIEW_DATE_RE.search(text)
    if not match:
        errors.append(f"{path}: invalid or missing review date (YYYY-MM-DD)")
    else:
        review_date = dt.date.fromisoformat(match.group(1))
        if review_date < dt.date.today():
            errors.append(f"{path}: review date expired ({review_date.isoformat()})")
    return errors


def main() -> int:
    errors: list[str] = []

    if not REQUIRED_MATRIX.exists():
        errors.append(f"Missing required matrix file: {REQUIRED_MATRIX}")

    if not ADR_DIR.exists():
        errors.append(f"Missing ADR directory: {ADR_DIR}")
    else:
        adrs = sorted(ADR_DIR.glob(ADR_GLOB))
        if not adrs:
            errors.append(f"No ADR files found matching {ADR_DIR / ADR_GLOB}")
        for adr in adrs:
            errors.extend(_validate_adr(adr))

    if errors:
        print("OSS guardrail check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("OSS guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
