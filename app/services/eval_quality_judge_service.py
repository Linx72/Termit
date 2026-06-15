"""Automated answer-quality rubric (1-5) for eval reports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class QualityJudgement:
    score: float
    rationale: str
    judge_model: str

    def as_dict(self) -> dict[str, object]:
        return {
            "quality_score": self.score,
            "quality_rationale": self.rationale,
            "judge_model": self.judge_model,
        }


def heuristic_quality_score(
    *,
    prompt: str,
    response: str,
    status: str,
    task_success: int = 0,
) -> QualityJudgement:
    """Fallback judge when cloud model is unavailable."""
    if status != "passed" or task_success == 0:
        return QualityJudgement(1.0, "Scenario failed or task not successful.", "heuristic")

    text = (response or "").strip()
    if not text:
        return QualityJudgement(1.0, "Empty response.", "heuristic")

    score = 2.5
    rationale_parts: list[str] = []

    if len(text) >= 80:
        score += 0.5
        rationale_parts.append("non-trivial response length")
    if re.search(r"(file|path|test|patch|function|class)\b", text, re.I):
        score += 0.5
        rationale_parts.append("mentions actionable code artifacts")
    if re.search(r"(because|therefore|step|fix|verify)\b", text, re.I):
        score += 0.5
        rationale_parts.append("contains reasoning markers")
    if "```" in text or "diff" in text.lower():
        score += 0.5
        rationale_parts.append("includes code/diff structure")

    score = max(1.0, min(5.0, score))
    rationale = ", ".join(rationale_parts) if rationale_parts else "basic pass heuristics"
    return QualityJudgement(score, rationale, "heuristic")


def build_judge_prompt(*, prompt: str, response: str, category: str) -> str:
    return (
        "Rate the assistant answer for a coding-agent scenario.\n"
        "Return JSON only: {\"score\": <1-5>, \"rationale\": \"...\"}\n"
        "Rubric: 1=wrong/empty, 3=partially useful, 5=actionable and verifiable.\n"
        f"Category: {category}\n"
        f"User prompt:\n{prompt[:2000]}\n\n"
        f"Assistant answer:\n{response[:4000]}\n"
    )


def parse_judge_json(raw: str) -> Optional[QualityJudgement]:
    text = raw.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    score_raw = payload.get("score")
    try:
        score = float(score_raw)
    except (TypeError, ValueError):
        return None
    score = max(1.0, min(5.0, score))
    rationale = str(payload.get("rationale", "")).strip() or "cloud judge"
    return QualityJudgement(score, rationale, "cloud-judge")


class EvalQualityJudgeService:
    def __init__(
        self,
        *,
        judge_model: str = "",
        llm_caller: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        self._judge_model = judge_model.strip()
        self._llm_caller = llm_caller

    @property
    def enabled(self) -> bool:
        return bool(self._judge_model and self._llm_caller)

    def judge_scenario(
        self,
        *,
        prompt: str,
        response: str,
        category: str,
        status: str,
        task_success: int = 0,
    ) -> QualityJudgement:
        if not self.enabled:
            return heuristic_quality_score(
                prompt=prompt,
                response=response,
                status=status,
                task_success=task_success,
            )
        judge_prompt = build_judge_prompt(prompt=prompt, response=response, category=category)
        try:
            raw = self._llm_caller(self._judge_model, judge_prompt)
        except Exception as exc:  # noqa: BLE001
            fallback = heuristic_quality_score(
                prompt=prompt,
                response=response,
                status=status,
                task_success=task_success,
            )
            return QualityJudgement(
                fallback.score,
                f"{fallback.rationale}; judge_error={exc}",
                "heuristic",
            )
        parsed = parse_judge_json(raw)
        if parsed is None:
            fallback = heuristic_quality_score(
                prompt=prompt,
                response=response,
                status=status,
                task_success=task_success,
            )
            return QualityJudgement(
                fallback.score,
                f"{fallback.rationale}; unparsable judge output",
                "heuristic",
            )
        return QualityJudgement(parsed.score, parsed.rationale, self._judge_model)

    def summarize_scores(self, scores: list[float]) -> dict[str, object]:
        if not scores:
            return {
                "quality_median": 0.0,
                "quality_mean": 0.0,
                "quality_min": 0.0,
                "quality_max": 0.0,
                "quality_count": 0,
            }
        ordered = sorted(scores)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            median = ordered[mid]
        else:
            median = (ordered[mid - 1] + ordered[mid]) / 2
        return {
            "quality_median": round(median, 3),
            "quality_mean": round(sum(scores) / len(scores), 3),
            "quality_min": round(min(scores), 3),
            "quality_max": round(max(scores), 3),
            "quality_count": len(scores),
        }
