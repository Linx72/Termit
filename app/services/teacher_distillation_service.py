"""Cloud-teacher distillation for Stage1 dataset enrichment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class DistillationResult:
    dataset_path: str
    sample_count: int
    teacher_model: str
    skipped: int
    errors: int

    def as_dict(self) -> dict[str, object]:
        return {
            "dataset_path": self.dataset_path,
            "sample_count": self.sample_count,
            "teacher_model": self.teacher_model,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def build_teacher_prompt(*, instruction: str, input_text: str, tool_schema_hint: str) -> str:
    context = input_text.strip()
    context_block = f"\nContext:\n{context[:3000]}\n" if context else ""
    return (
        "You are a senior coding agent teacher for the Termit orchestrator.\n"
        "Produce the best final answer for the student model to imitate.\n"
        "Prefer: minimal diffs, explicit file paths, runnable verify steps, JSON tool actions when needed.\n"
        f"{tool_schema_hint}\n"
        f"Task:\n{instruction[:2000]}{context_block}\n"
        "Return only the ideal assistant answer."
    )


class TeacherDistillationService:
    def __init__(
        self,
        *,
        teacher_model: str,
        teacher_fallback_model: str = "",
        cloud_teacher_model: str = "",
        datasets_dir: str = "./data/finetune/datasets",
        llm_caller: Optional[Callable[[str, str], str]] = None,
        max_samples: int = 200,
    ) -> None:
        self._teacher_model = teacher_model.strip()
        self._teacher_fallback_model = teacher_fallback_model.strip()
        self._cloud_teacher_model = cloud_teacher_model.strip()
        self._datasets_dir = Path(datasets_dir)
        self._llm_caller = llm_caller
        self._max_samples = max(1, min(max_samples, 2000))
        self._datasets_dir.mkdir(parents=True, exist_ok=True)

    def resolve_teacher_model(self) -> str:
        if self._cloud_teacher_model:
            return self._cloud_teacher_model
        if self._teacher_fallback_model.startswith("openai_compat:"):
            return self._teacher_fallback_model
        return self._teacher_model

    def distill_samples(
        self,
        samples: list[dict[str, str]],
        *,
        name: str = "teacher-distill",
        tool_schema_hint: str = 'Tool JSON example: {"action":"tool","tool":"read_file","arguments":{"path":"app","file":"main.py"}}',
    ) -> DistillationResult:
        teacher = self.resolve_teacher_model()
        if self._llm_caller is None:
            raise ValueError("Teacher distillation requires an LLM caller (cloud/openai_compat).")

        slug = name.strip().replace(" ", "_").lower()[:40] or "teacher-distill"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = self._datasets_dir / f"{slug}_{timestamp}.jsonl"

        exported = 0
        skipped = 0
        errors = 0
        with out_path.open("w", encoding="utf-8") as handle:
            for row in samples[: self._max_samples]:
                instruction = str(row.get("instruction", "")).strip()
                if len(instruction) < 8:
                    skipped += 1
                    continue
                input_text = str(row.get("input", "")).strip()
                prompt = build_teacher_prompt(
                    instruction=instruction,
                    input_text=input_text,
                    tool_schema_hint=tool_schema_hint,
                )
                try:
                    output = self._llm_caller(teacher, prompt).strip()
                except Exception:  # noqa: BLE001
                    errors += 1
                    continue
                if len(output) < 16:
                    skipped += 1
                    continue
                payload = {
                    "instruction": instruction,
                    "input": input_text,
                    "output": output,
                    "source": "teacher_distill",
                    "category": str(row.get("category", "coding")),
                    "teacher_model": teacher,
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                exported += 1

        if exported < 1:
            raise ValueError(
                f"Teacher distillation produced 0 samples (skipped={skipped}, errors={errors})."
            )

        return DistillationResult(
            dataset_path=str(out_path),
            sample_count=exported,
            teacher_model=teacher,
            skipped=skipped,
            errors=errors,
        )
