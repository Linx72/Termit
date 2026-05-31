from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

# Conservative patterns — only used when output is short and looks like a refusal.
_REFUSAL_PATTERNS = (
    re.compile(r"^i (?:cannot|can't) help", re.I),
    re.compile(r"^as an ai (?:language )?model", re.I),
    re.compile(r"^i'?m (?:sorry|unable to)", re.I),
)

_SOURCE_PRIORITY = {
    "feedback": 40,
    "agent_run": 30,
    "task": 25,
    "chat_session": 15,
}


@dataclass(frozen=True)
class CuratorConfig:
    deduplicate: bool = True
    min_output_chars: int = 12
    max_output_chars: int = 12000
    skip_error_patterns: bool = True
    stratified_balance: bool = False
    max_per_category: Optional[int] = None


@dataclass
class CurationStats:
    raw_count: int = 0
    exported_count: int = 0
    filtered_quality: int = 0
    filtered_duplicate: int = 0
    filtered_category_cap: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "raw_count": self.raw_count,
            "exported_count": self.exported_count,
            "filtered_quality": self.filtered_quality,
            "filtered_duplicate": self.filtered_duplicate,
            "filtered_category_cap": self.filtered_category_cap,
        }


def _sample_score(row: dict[str, str]) -> float:
    source = str(row.get("source", ""))
    score = float(_SOURCE_PRIORITY.get(source, 10))
    rating = row.get("rating")
    if rating is not None:
        try:
            score += float(rating) * 8.0
        except (TypeError, ValueError):
            pass
    if str(row.get("input", "")).strip():
        score += 4.0
    if str(row.get("trajectory", "")).strip():
        score += 5.0
    output_len = len(str(row.get("output", "")))
    score += min(output_len / 120.0, 6.0)
    return score


def _instruction_key(row: dict[str, str]) -> str:
    instruction = str(row.get("instruction", "")).strip().lower()
    digest = hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:16]
    return digest


def _looks_like_refusal(output: str) -> bool:
    text = output.strip()
    if len(text) > 160:
        return False
    return any(pattern.search(text) for pattern in _REFUSAL_PATTERNS)


def _passes_quality(row: dict[str, str], config: CuratorConfig) -> bool:
    output = str(row.get("output", "")).strip()
    instruction = str(row.get("instruction", "")).strip()
    if len(instruction) < 4:
        return False
    if len(output) < config.min_output_chars:
        return False
    if len(output) > config.max_output_chars:
        return False
    if config.skip_error_patterns and _looks_like_refusal(output):
        return False
    if str(row.get("skip_export", "")).lower() in {"1", "true", "yes"}:
        return False
    return True


def curate_samples(
    samples: list[dict[str, str]],
    config: Optional[CuratorConfig] = None,
) -> tuple[list[dict], CurationStats]:
    cfg = config or CuratorConfig()
    stats = CurationStats(raw_count=len(samples))
    kept: list[dict[str, str]] = []

    for row in samples:
        normalized = {key: str(value) for key, value in row.items() if value is not None}
        if not _passes_quality(normalized, cfg):
            stats.filtered_quality += 1
            continue
        normalized["quality_score"] = f"{_sample_score(normalized):.2f}"
        kept.append(normalized)

    if cfg.deduplicate and kept:
        best_by_key: dict[str, dict[str, str]] = {}
        for row in kept:
            key = _instruction_key(row)
            existing = best_by_key.get(key)
            if existing is None or _sample_score(row) > _sample_score(existing):
                if existing is not None:
                    stats.filtered_duplicate += 1
                best_by_key[key] = row
            else:
                stats.filtered_duplicate += 1
        kept = list(best_by_key.values())

    if cfg.stratified_balance and cfg.max_per_category:
        capped: list[dict[str, str]] = []
        per_category: dict[str, int] = {}
        for row in kept:
            category = str(row.get("category", "general") or "general")
            count = per_category.get(category, 0)
            if count >= cfg.max_per_category:
                stats.filtered_category_cap += 1
                continue
            per_category[category] = count + 1
            capped.append(row)
        kept = capped

    stats.exported_count = len(kept)
    return kept, stats


def export_row(row: dict[str, str]) -> dict[str, str]:
    """Strip internal-only fields before writing JSONL."""
    allowed = {
        "instruction",
        "input",
        "output",
        "source",
        "category",
        "session_id",
        "task_id",
        "run_id",
        "rating",
        "quality_score",
    }
    return {key: value for key, value in row.items() if key in allowed and value}
