from __future__ import annotations

import json
from pathlib import Path

from app.services.training_signal_store import normalize_capture_instruction


DPO_CONTRACT_VERSION = "1.0"


def _normalize_instruction(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def _instruction_tokens(text: str) -> set[str]:
    return {token for token in _normalize_instruction(text).split() if len(token) >= 3}


def _token_overlap_score(left: str, right: str) -> float:
    left_tokens = _instruction_tokens(left)
    right_tokens = _instruction_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return len(intersection) / max(1, len(union))


def _resolve_chosen_for_negative(
    neg: dict[str, str],
    *,
    positive_by_instruction: dict[str, tuple[float, str]],
    positive_by_run_id: dict[str, tuple[float, str]],
    positives: list[dict[str, str]],
    min_chosen_chars: int,
    min_overlap: float = 0.45,
) -> str:
    embedded = str(neg.get("chosen", "")).strip()
    if len(embedded) >= min_chosen_chars:
        return embedded

    instruction = str(neg.get("instruction", "")).strip()
    normalized = _normalize_instruction(instruction)
    chosen_entry = positive_by_instruction.get(normalized)
    if chosen_entry and len(chosen_entry[1]) >= min_chosen_chars:
        return chosen_entry[1]

    run_id = str(neg.get("run_id", "")).strip()
    if run_id:
        run_entry = positive_by_run_id.get(run_id)
        if run_entry and len(run_entry[1]) >= min_chosen_chars:
            return run_entry[1]

    best_score = 0.0
    best_output = ""
    for row in positives:
        output = str(row.get("output", "")).strip()
        if len(output) < min_chosen_chars:
            continue
        score = _token_overlap_score(instruction, str(row.get("instruction", "")))
        quality = float(row.get("quality_score", "0") or 0)
        combined = score + (0.05 * quality)
        if combined > best_score:
            best_score = combined
            best_output = output
    if best_score + 1e-9 >= min_overlap and len(best_output) >= min_chosen_chars:
        return best_output
    return ""


CATEGORY_FALLBACK_MAP: dict[str, tuple[str, ...]] = {
    "tool_loop_negative": ("tool_loop", "coding", "general"),
    "patch_revert": ("coding", "tool_loop", "general"),
}


def _category_fallback_chosen(
    neg: dict[str, str],
    positives: list[dict[str, str]],
    *,
    min_chosen_chars: int,
) -> str:
    category = str(neg.get("category", "tool_loop_negative"))
    pools = CATEGORY_FALLBACK_MAP.get(category, ("general", "coding", "tool_loop"))
    best_score = -1.0
    best_output = ""
    for pool in pools:
        for row in positives:
            if str(row.get("category", "")) != pool:
                continue
            output = str(row.get("output", "")).strip()
            if len(output) < min_chosen_chars:
                continue
            quality = float(row.get("quality_score", "0") or 0)
            if quality > best_score or (quality == best_score and len(output) > len(best_output)):
                best_score = quality
                best_output = output
    return best_output


def build_dpo_pairs(
    negatives: list[dict[str, str]],
    positives: list[dict[str, str]],
    *,
    min_chosen_chars: int = 12,
    allow_category_fallback: bool = True,
) -> list[dict[str, str]]:
    """Pair DPO negatives with best-matching successful outputs (instruction/run/overlap)."""
    positive_by_instruction: dict[str, tuple[float, str]] = {}
    positive_by_run_id: dict[str, tuple[float, str]] = {}
    for row in positives:
        instruction = _normalize_instruction(normalize_capture_instruction(str(row.get("instruction", ""))))
        output = str(row.get("output", "")).strip()
        if len(instruction) < 4 or len(output) < min_chosen_chars:
            continue
        score = float(row.get("quality_score", "0") or 0)
        existing = positive_by_instruction.get(instruction)
        if existing is None or score > existing[0]:
            positive_by_instruction[instruction] = (score, output)
        run_id = str(row.get("run_id", "")).strip()
        if run_id:
            existing_run = positive_by_run_id.get(run_id)
            if existing_run is None or score > existing_run[0]:
                positive_by_run_id[run_id] = (score, output)

    pairs: list[dict[str, str]] = []
    for neg in negatives:
        instruction = normalize_capture_instruction(str(neg.get("instruction", "")))
        rejected = str(neg.get("rejected", neg.get("output", ""))).strip()
        if len(instruction) < 4 or len(rejected) < min_chosen_chars:
            continue
        neg_for_match = {**neg, "instruction": instruction}
        chosen = _resolve_chosen_for_negative(
            neg_for_match,
            positive_by_instruction=positive_by_instruction,
            positive_by_run_id=positive_by_run_id,
            positives=positives,
            min_chosen_chars=min_chosen_chars,
        )
        source = "dpo_pair"
        if len(chosen) < min_chosen_chars and allow_category_fallback:
            chosen = _category_fallback_chosen(neg_for_match, positives, min_chosen_chars=min_chosen_chars)
            source = "dpo_category_fallback"
        if len(chosen) < min_chosen_chars:
            continue
        pairs.append(
            {
                "instruction": instruction,
                "input": str(neg.get("input", "")).strip(),
                "chosen": chosen,
                "rejected": rejected,
                "source": source,
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
