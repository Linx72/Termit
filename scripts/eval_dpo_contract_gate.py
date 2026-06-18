#!/usr/bin/env python3
"""Validate a DPO JSONL dataset against the Termit DPO contract (exit 0/1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.finetune_dpo_export import DPO_CONTRACT_VERSION, validate_dpo_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="DPO dataset contract gate")
    parser.add_argument("--dataset", default="", help="Path to dpo.jsonl")
    parser.add_argument("--min-text-chars", type=int, default=4)
    parser.add_argument("--min-rows", type=int, default=1)
    args = parser.parse_args()

    dataset_path = args.dataset.strip()
    if not dataset_path and not sys.stdin.isatty():
        payload = json.load(sys.stdin)
        if isinstance(payload, dict):
            dataset_path = str(payload.get("dataset_path", "")).strip()

    if not dataset_path:
        print("DPO contract gate: dataset path is required.", file=sys.stderr)
        return 2

    path = Path(dataset_path)
    if not path.exists():
        print(f"DPO contract gate: file not found: {path}", file=sys.stderr)
        return 1

    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            rows.append({})
            continue
        rows.append(item if isinstance(item, dict) else {})

    contract = validate_dpo_rows(rows, min_text_chars=max(1, args.min_text_chars))
    print(json.dumps(contract, indent=2, ensure_ascii=False))

    if int(contract.get("valid_rows", 0)) < max(1, args.min_rows):
        print(
            f"DPO contract gate failed: valid_rows={contract.get('valid_rows')} "
            f"< min_rows={args.min_rows}.",
            file=sys.stderr,
        )
        return 1
    if not bool(contract.get("valid", False)):
        print(
            f"DPO contract gate failed: contract_version={DPO_CONTRACT_VERSION}, "
            f"invalid_rows={contract.get('invalid_rows')}.",
            file=sys.stderr,
        )
        return 1

    print(
        f"DPO contract gate passed: {contract.get('valid_rows')} rows, "
        f"contract_version={DPO_CONTRACT_VERSION}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
