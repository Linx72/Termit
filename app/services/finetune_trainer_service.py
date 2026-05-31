from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class FinetuneTrainResult:
    trainer_mode: str
    status: str
    output_model: Optional[str] = None
    modelfile_path: Optional[str] = None
    command: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "trainer_mode": self.trainer_mode,
            "status": self.status,
            "output_model": self.output_model,
            "modelfile_path": self.modelfile_path,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "detail": self.detail,
        }


class FinetuneTrainerService:
    """Build Modelfile from dataset and optionally run `ollama create`."""

    def __init__(
        self,
        *,
        modelfiles_dir: str = "./data/finetune/modelfiles",
        ollama_bin: str = "ollama",
        default_output_model: str = "termit-core-ft",
        trainer_mode: str = "ollama",
        train_timeout_seconds: int = 600,
        max_prompt_examples: int = 8,
    ) -> None:
        self.modelfiles_dir = Path(modelfiles_dir)
        self.ollama_bin = ollama_bin
        self.default_output_model = default_output_model
        self.trainer_mode = trainer_mode.strip().lower() or "off"
        self.train_timeout_seconds = max(30, train_timeout_seconds)
        self.max_prompt_examples = max(1, min(max_prompt_examples, 32))
        self.modelfiles_dir.mkdir(parents=True, exist_ok=True)

    @property
    def auto_train_enabled(self) -> bool:
        return self.trainer_mode not in {"", "off", "none", "false"}

    def train_dataset(
        self,
        *,
        dataset_path: str,
        base_model: str,
        output_model: Optional[str] = None,
        trainer_mode: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> FinetuneTrainResult:
        mode = (trainer_mode or self.trainer_mode).strip().lower()
        if mode in {"", "off", "none", "false"}:
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="skipped",
                detail="Trainer disabled (TERMIT_FINETUNE_TRAINER=off).",
            )

        dataset = Path(dataset_path)
        if not dataset.exists():
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="failed",
                detail=f"Dataset not found: {dataset_path}",
            )

        resolved_output = (output_model or self.default_output_model).strip()
        slug = job_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        modelfile_path = self.modelfiles_dir / f"{slug}.Modelfile"
        modelfile_body = self.build_modelfile(base_model=base_model, dataset_path=dataset)
        modelfile_path.write_text(modelfile_body, encoding="utf-8")

        if mode == "modelfile":
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="completed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                command=f"{self.ollama_bin} create {resolved_output} -f {modelfile_path}",
                detail="Modelfile written; run ollama create manually or use trainer_mode=ollama.",
            )

        if mode != "ollama":
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="failed",
                modelfile_path=str(modelfile_path),
                detail=f"Unknown trainer mode: {mode}",
            )

        if shutil.which(self.ollama_bin) is None:
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="failed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                command=f"{self.ollama_bin} create {resolved_output} -f {modelfile_path}",
                detail=f"Binary not found: {self.ollama_bin}",
            )

        command = [self.ollama_bin, "create", resolved_output, "-f", str(modelfile_path)]
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.train_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="failed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                command=" ".join(command),
                stdout=(exc.stdout or "")[:4000] if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "")[:4000] if isinstance(exc.stderr, str) else "",
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail=f"Training timed out after {self.train_timeout_seconds}s",
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        ok = completed.returncode == 0
        return FinetuneTrainResult(
            trainer_mode=mode,
            status="completed" if ok else "failed",
            output_model=resolved_output if ok else None,
            modelfile_path=str(modelfile_path),
            command=" ".join(command),
            stdout=(completed.stdout or "")[:4000],
            stderr=(completed.stderr or "")[:4000],
            duration_ms=duration_ms,
            detail="Ollama model created." if ok else f"ollama create exit {completed.returncode}",
        )

    def build_modelfile(self, *, base_model: str, dataset_path: Path) -> str:
        from_ref = base_model.split(":", 1)[-1] if ":" in base_model else base_model
        examples = self._load_examples(dataset_path)
        system_lines = [
            "You are Termit, a domain-specific coding assistant trained on this repository.",
            "Follow project conventions, cite file paths, and prefer actionable steps.",
        ]
        if examples:
            system_lines.append("")
            system_lines.append("Reference examples from recent Termit runs:")
            for idx, row in enumerate(examples, start=1):
                instruction = row.get("instruction", "").strip()
                output = row.get("output", "").strip()
                if not instruction and not output:
                    continue
                snippet = output[:400].replace("\n", " ")
                system_lines.append(f"{idx}. Q: {instruction[:200]}")
                system_lines.append(f"   A: {snippet}")

        system_block = "\n".join(system_lines)
        return (
            f"FROM {from_ref}\n"
            "PARAMETER temperature 0.2\n"
            "PARAMETER num_ctx 8192\n"
            f'SYSTEM """{system_block}"""\n'
        )

    def _load_examples(self, dataset_path: Path) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for line in dataset_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(
                    {
                        "instruction": str(item.get("instruction", "")),
                        "output": str(item.get("output", "")),
                    }
                )
            if len(rows) >= self.max_prompt_examples:
                break
        return rows
