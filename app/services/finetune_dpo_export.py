from __future__ import annotations

import json
from pathlib import Path


DPO_CONTRACT_VERSION = "1.0"


def build_dpo_pairs(
    negatives: list[dict[str, str]],
    positives: list[dict[str, str]],
    *,
    min_chosen_chars: int = 12,
) -> list[dict[str, str]]:
    """Pair DPO negatives with best-matching successful outputs (same instruction)."""
    positive_by_instruction: dict[str, tuple[float, str]] = {}
    for row in positives:
        instruction = str(row.get("instruction", "")).strip().lower()
        output = str(row.get("output", "")).strip()
        if len(instruction) < 4 or len(output) < min_chosen_chars:
            continue
        score = float(row.get("quality_score", "0") or 0)
        existing = positive_by_instruction.get(instruction)
        if existing is None or score > existing[0]:
            positive_by_instruction[instruction] = (score, output)

    pairs: list[dict[str, str]] = []
    for neg in negatives:
        instruction = str(neg.get("instruction", "")).strip()
        rejected = str(neg.get("rejected", neg.get("output", ""))).strip()
        if len(instruction) < 4 or len(rejected) < min_chosen_chars:
            continue
        chosen_entry = positive_by_instruction.get(instruction.lower())
        chosen = chosen_entry[1] if chosen_entry else ""
        if len(chosen) < min_chosen_chars:
            continue
        pairs.append(
            {
                "instruction": instruction,
                "input": str(neg.get("input", "")).strip(),
                "chosen": chosen,
                "rejected": rejected,
                "source": "dpo_pair",
                "category": str(neg.get("category", "tool_loop_negative")),
                "run_id": str(neg.get("run_id", "")),
            }
        )
    return pairs


def write_dpo_jsonl(path: Path | str, rows: list[dict[str, str]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def validate_dpo_rows(
    rows: list[dict[str, object]],
    *,
    min_text_chars: int = 4,
) -> dict[str, object]:
    required = ("instruction", "chosen", "rejected")
    valid = 0
    invalid = 0
    missing_field_rows = 0
    too_short_rows = 0
    same_answer_rows = 0

    for row in rows:
        if not isinstance(row, dict):
            invalid += 1
            continue
        if any(not str(row.get(field, "")).strip() for field in required):
            invalid += 1
            missing_field_rows += 1
            continue
        instruction = str(row.get("instruction", "")).strip()
        chosen = str(row.get("chosen", "")).strip()
        rejected = str(row.get("rejected", "")).strip()
        if min(len(instruction), len(chosen), len(rejected)) < min_text_chars:
            invalid += 1
            too_short_rows += 1
            continue
        if chosen == rejected:
            invalid += 1
            same_answer_rows += 1
            continue
        valid += 1

    total = valid + invalid
    is_valid = total > 0 and invalid == 0
    return {
        "contract_version": DPO_CONTRACT_VERSION,
        "valid": is_valid,
        "total": total,
        "valid_rows": valid,
        "invalid_rows": invalid,
        "missing_field_rows": missing_field_rows,
        "too_short_rows": too_short_rows,
        "same_answer_rows": same_answer_rows,
    }
