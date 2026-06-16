from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from app.services.finetune_gguf_converter import (
    convert_adapter_to_gguf,
    write_convert_manifest,
)


def resolve_ollama_host(
    explicit: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[str]:
    if explicit and explicit.strip():
        return explicit.strip()
    env_host = os.getenv("OLLAMA_HOST", "").strip()
    if env_host:
        return env_host
    if base_url:
        parsed = urlparse(base_url)
        if parsed.netloc:
            return parsed.netloc
    return None


@dataclass(frozen=True)
class FinetuneTrainResult:
    trainer_mode: str
    status: str
    output_model: Optional[str] = None
    modelfile_path: Optional[str] = None
    adapter_path: Optional[str] = None
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
            "adapter_path": self.adapter_path,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "detail": self.detail,
        }


class FinetuneTrainerService:
    """Build Modelfile from dataset; train via Ollama create or Unsloth QLoRA (hf mode)."""

    def __init__(
        self,
        *,
        modelfiles_dir: str = "./data/finetune/modelfiles",
        adapters_dir: str = "./data/finetune/adapters",
        ollama_bin: str = "ollama",
        ollama_host: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        default_output_model: str = "termit-core-ft",
        trainer_mode: str = "ollama",
        train_timeout_seconds: int = 600,
        max_prompt_examples: int = 8,
        hf_dry_run: bool = True,
        hf_epochs: int = 1,
        hf_lora_rank: int = 16,
        hf_max_samples: int = 500,
        hf_auto_gguf: bool = True,
        hf_auto_ollama: bool = False,
        llama_cpp_path: str = "",
    ) -> None:
        self.modelfiles_dir = Path(modelfiles_dir)
        self.adapters_dir = Path(adapters_dir)
        self.ollama_bin = ollama_bin
        self.ollama_host = resolve_ollama_host(ollama_host, ollama_base_url)
        self.default_output_model = default_output_model
        self.trainer_mode = trainer_mode.strip().lower() or "off"
        self.train_timeout_seconds = max(30, train_timeout_seconds)
        self.max_prompt_examples = max(1, min(max_prompt_examples, 32))
        self.hf_dry_run = hf_dry_run
        self.hf_epochs = max(1, hf_epochs)
        self.hf_lora_rank = max(4, min(hf_lora_rank, 128))
        self.hf_max_samples = max(1, min(hf_max_samples, 5000))
        self.hf_auto_gguf = hf_auto_gguf
        self.hf_auto_ollama = hf_auto_ollama
        self.llama_cpp_path = llama_cpp_path.strip()
        self.modelfiles_dir.mkdir(parents=True, exist_ok=True)
        self.adapters_dir.mkdir(parents=True, exist_ok=True)

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
        repo_profile_id: Optional[str] = None,
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
        adapter_gguf = self.resolve_adapter_gguf(resolved_output, repo_profile_id=repo_profile_id)
        modelfile_path = self.modelfiles_dir / f"{slug}.Modelfile"
        modelfile_body = self.build_modelfile(
            base_model=base_model,
            dataset_path=dataset,
            adapter_gguf=adapter_gguf,
        )
        modelfile_path.write_text(modelfile_body, encoding="utf-8")

        if mode == "modelfile":
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="completed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(adapter_gguf) if adapter_gguf else None,
                command=f"{self.ollama_bin} create {resolved_output} -f {modelfile_path}",
                detail="Modelfile written; run ollama create manually or use trainer_mode=ollama.",
            )

        if mode == "hf":
            return self._train_hf(
                dataset=dataset,
                base_model=base_model,
                resolved_output=resolved_output,
                slug=slug,
                modelfile_path=modelfile_path,
                repo_profile_id=repo_profile_id,
            )

        if mode in {"hf_dpo", "dpo"}:
            return self._train_hf_dpo(
                dataset=dataset,
                base_model=base_model,
                resolved_output=resolved_output,
                slug=slug,
                modelfile_path=modelfile_path,
                repo_profile_id=repo_profile_id,
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
                adapter_path=str(adapter_gguf) if adapter_gguf else None,
                command=f"{self.ollama_bin} create {resolved_output} -f {modelfile_path}",
                detail=f"Binary not found: {self.ollama_bin}",
            )

        ollama_err = self._ensure_ollama_reachable()
        if ollama_err:
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="failed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(adapter_gguf) if adapter_gguf else None,
                command=f"{self.ollama_bin} create {resolved_output} -f {modelfile_path}",
                detail=ollama_err,
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
                env=self._ollama_subprocess_env(),
            )
        except subprocess.TimeoutExpired as exc:
            return FinetuneTrainResult(
                trainer_mode=mode,
                status="failed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(adapter_gguf) if adapter_gguf else None,
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
            adapter_path=str(adapter_gguf) if adapter_gguf else None,
            command=" ".join(command),
            stdout=(completed.stdout or "")[:4000],
            stderr=(completed.stderr or "")[:4000],
            duration_ms=duration_ms,
            detail="Ollama model created." if ok else f"ollama create exit {completed.returncode}",
        )

    def resolve_adapter_gguf(
        self,
        output_model: str,
        *,
        repo_profile_id: Optional[str] = None,
    ) -> Optional[Path]:
        candidates: list[Path] = []
        slug = output_model.replace(":", "_").replace("/", "_")
        if repo_profile_id:
            repo_dir = self.adapters_dir / repo_profile_id.strip()
            candidates.extend(
                [
                    repo_dir / f"{slug}.gguf",
                    repo_dir / "adapter.gguf",
                    repo_dir / f"{slug}_adapter.gguf",
                ]
            )
        model_dir = self.adapters_dir / slug
        candidates.extend(
            [
                model_dir / "adapter.gguf",
                model_dir / f"{slug}.gguf",
                self.adapters_dir / f"{slug}.gguf",
                self.adapters_dir / f"{slug}_adapter.gguf",
            ]
        )
        for path in candidates:
            if path.exists() and path.is_file():
                return path.resolve()
        return None

    def _train_hf(
        self,
        *,
        dataset: Path,
        base_model: str,
        resolved_output: str,
        slug: str,
        modelfile_path: Path,
        repo_profile_id: Optional[str],
    ) -> FinetuneTrainResult:
        from_ref = base_model.split(":", 1)[-1] if ":" in base_model else base_model
        if repo_profile_id:
            output_dir = self.adapters_dir / repo_profile_id.strip() / resolved_output.replace(":", "_")
        else:
            output_dir = self.adapters_dir / resolved_output.replace(":", "_")
        output_dir.mkdir(parents=True, exist_ok=True)

        root = Path(__file__).resolve().parents[2]
        trainer_script = root / "scripts" / "unsloth_qlora_train.py"
        command = [
            sys.executable,
            str(trainer_script),
            "--dataset",
            str(dataset),
            "--base-model",
            from_ref,
            "--output-dir",
            str(output_dir),
            "--epochs",
            str(self.hf_epochs),
            "--lora-rank",
            str(self.hf_lora_rank),
            "--max-samples",
            str(self.hf_max_samples),
        ]

        if self.hf_dry_run:
            return FinetuneTrainResult(
                trainer_mode="hf",
                status="completed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(output_dir),
                command=" ".join(command),
                detail=(
                    "HF dry-run: Unsloth command prepared. "
                    "Set TERMIT_FINETUNE_HF_DRY_RUN=false and install unsloth to execute."
                ),
            )

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
                trainer_mode="hf",
                status="failed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(output_dir),
                command=" ".join(command),
                stdout=(exc.stdout or "")[:4000] if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "")[:4000] if isinstance(exc.stderr, str) else "",
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail=f"HF training timed out after {self.train_timeout_seconds}s",
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        if completed.returncode == 2:
            return FinetuneTrainResult(
                trainer_mode="hf",
                status="completed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(output_dir),
                command=" ".join(command),
                stdout=(completed.stdout or "")[:4000],
                stderr=(completed.stderr or "")[:4000],
                duration_ms=duration_ms,
                detail="Unsloth not installed; command saved for manual GPU run.",
            )
        ok = completed.returncode == 0
        gguf_detail = ""
        adapter_gguf = self.resolve_adapter_gguf(resolved_output, repo_profile_id=repo_profile_id)
        if ok and self.hf_auto_gguf:
            gguf_target = self._gguf_target_path(
                resolved_output=resolved_output,
                repo_profile_id=repo_profile_id,
            )
            convert_result = convert_adapter_to_gguf(
                adapter_dir=output_dir,
                output_gguf=gguf_target,
                base_model=from_ref,
                llama_cpp_path=self.llama_cpp_path or None,
                timeout_seconds=self.train_timeout_seconds,
            )
            write_convert_manifest(output_dir, convert_result)
            gguf_detail = convert_result.detail
            if convert_result.gguf_path:
                adapter_gguf = Path(convert_result.gguf_path)

        if ok and adapter_gguf is not None:
            modelfile_path.write_text(
                self.build_modelfile(
                    base_model=base_model,
                    dataset_path=dataset,
                    adapter_gguf=adapter_gguf,
                ),
                encoding="utf-8",
            )

        ollama_detail = ""
        if ok and self.hf_auto_ollama and adapter_gguf is not None:
            ollama_result = self._run_ollama_create(
                modelfile_path=modelfile_path,
                output_model=resolved_output,
            )
            ollama_detail = ollama_result.detail
            if ollama_result.status != "completed":
                ok = False

        detail_parts = []
        if ok:
            detail_parts.append("Unsloth QLoRA completed.")
        else:
            detail_parts.append(f"Unsloth trainer exit {completed.returncode}")
        if gguf_detail:
            detail_parts.append(gguf_detail)
        if ollama_detail:
            detail_parts.append(ollama_detail)
        if ok and adapter_gguf is None:
            detail_parts.append("Convert adapter to GGUF for Ollama ADAPTER.")

        return FinetuneTrainResult(
            trainer_mode="hf",
            status="completed" if ok else "failed",
            output_model=resolved_output if ok else None,
            modelfile_path=str(modelfile_path),
            adapter_path=str(adapter_gguf or output_dir),
            command=" ".join(command),
            stdout=(completed.stdout or "")[:4000],
            stderr=(completed.stderr or "")[:4000],
            duration_ms=duration_ms,
            detail=" ".join(detail_parts),
        )

    def _train_hf_dpo(
        self,
        *,
        dataset: Path,
        base_model: str,
        resolved_output: str,
        slug: str,
        modelfile_path: Path,
        repo_profile_id: Optional[str],
    ) -> FinetuneTrainResult:
        from_ref = base_model.split(":", 1)[-1] if ":" in base_model else base_model
        if repo_profile_id:
            output_dir = self.adapters_dir / repo_profile_id.strip() / resolved_output.replace(":", "_")
        else:
            output_dir = self.adapters_dir / resolved_output.replace(":", "_")
        output_dir.mkdir(parents=True, exist_ok=True)

        root = Path(__file__).resolve().parents[2]
        trainer_script = root / "scripts" / "unsloth_dpo_train.py"
        command = [
            sys.executable,
            str(trainer_script),
            "--dataset",
            str(dataset),
            "--base-model",
            from_ref,
            "--output-dir",
            str(output_dir),
            "--epochs",
            str(self.hf_epochs),
            "--lora-rank",
            str(self.hf_lora_rank),
            "--max-samples",
            str(self.hf_max_samples),
        ]

        if self.hf_dry_run:
            return FinetuneTrainResult(
                trainer_mode="hf_dpo",
                status="completed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(output_dir),
                command=" ".join(command),
                detail=(
                    "HF DPO dry-run: Unsloth DPO command prepared. "
                    "Set TERMIT_FINETUNE_HF_DRY_RUN=false and install unsloth to execute."
                ),
            )

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
                trainer_mode="hf_dpo",
                status="failed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(output_dir),
                command=" ".join(command),
                stdout=(exc.stdout or "")[:4000] if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "")[:4000] if isinstance(exc.stderr, str) else "",
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail=f"HF DPO training timed out after {self.train_timeout_seconds}s",
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        if completed.returncode == 2:
            return FinetuneTrainResult(
                trainer_mode="hf_dpo",
                status="completed",
                output_model=resolved_output,
                modelfile_path=str(modelfile_path),
                adapter_path=str(output_dir),
                command=" ".join(command),
                stdout=(completed.stdout or "")[:4000],
                stderr=(completed.stderr or "")[:4000],
                duration_ms=duration_ms,
                detail="Unsloth DPO stack not installed; command saved for manual GPU run.",
            )
        ok = completed.returncode == 0
        return FinetuneTrainResult(
            trainer_mode="hf_dpo",
            status="completed" if ok else "failed",
            output_model=resolved_output if ok else None,
            modelfile_path=str(modelfile_path),
            adapter_path=str(output_dir),
            command=" ".join(command),
            stdout=(completed.stdout or "")[:4000],
            stderr=(completed.stderr or "")[:4000],
            duration_ms=duration_ms,
            detail="Unsloth DPO training completed." if ok else f"Unsloth DPO trainer exit {completed.returncode}",
        )

    def _gguf_target_path(
        self,
        *,
        resolved_output: str,
        repo_profile_id: Optional[str],
    ) -> Path:
        slug = resolved_output.replace(":", "_").replace("/", "_")
        if repo_profile_id:
            return (self.adapters_dir / repo_profile_id.strip() / f"{slug}.gguf").resolve()
        return (self.adapters_dir / f"{slug}.gguf").resolve()

    def _run_ollama_create(
        self,
        *,
        modelfile_path: Path,
        output_model: str,
    ) -> FinetuneTrainResult:
        if shutil.which(self.ollama_bin) is None:
            return FinetuneTrainResult(
                trainer_mode="hf",
                status="failed",
                output_model=output_model,
                modelfile_path=str(modelfile_path),
                detail=f"Binary not found: {self.ollama_bin}",
            )
        ollama_err = self._ensure_ollama_reachable()
        if ollama_err:
            return FinetuneTrainResult(
                trainer_mode="hf",
                status="failed",
                output_model=output_model,
                modelfile_path=str(modelfile_path),
                detail=ollama_err,
            )
        command = [self.ollama_bin, "create", output_model, "-f", str(modelfile_path)]
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.train_timeout_seconds,
                check=False,
                env=self._ollama_subprocess_env(),
            )
        except subprocess.TimeoutExpired:
            return FinetuneTrainResult(
                trainer_mode="hf",
                status="failed",
                output_model=output_model,
                modelfile_path=str(modelfile_path),
                command=" ".join(command),
                detail=f"ollama create timed out after {self.train_timeout_seconds}s",
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        ok = completed.returncode == 0
        return FinetuneTrainResult(
            trainer_mode="hf",
            status="completed" if ok else "failed",
            output_model=output_model if ok else None,
            modelfile_path=str(modelfile_path),
            command=" ".join(command),
            stdout=(completed.stdout or "")[:4000],
            stderr=(completed.stderr or "")[:4000],
            duration_ms=duration_ms,
            detail="Ollama model created from HF adapter." if ok else f"ollama create exit {completed.returncode}",
        )

    def _ollama_subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.ollama_host:
            env["OLLAMA_HOST"] = self.ollama_host
        return env

    def _ensure_ollama_reachable(self) -> Optional[str]:
        host = self.ollama_host or "127.0.0.1:11434"
        tags_url = f"http://{host}/api/tags"
        if self._probe_ollama(tags_url):
            return None

        root = Path(__file__).resolve().parents[2]
        script = root / "scripts" / "start_ollama_local.sh"
        if not script.exists():
            return f"Ollama not reachable at {host}"

        subprocess.run(
            ["/bin/bash", str(script)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=self._ollama_subprocess_env(),
        )
        time.sleep(1.5)
        if self._probe_ollama(tags_url):
            return None
        return f"Ollama not reachable at {host} after auto-start"

    @staticmethod
    def _probe_ollama(tags_url: str) -> bool:
        try:
            with urllib.request.urlopen(tags_url, timeout=3) as response:
                return int(getattr(response, "status", 200)) == 200
        except (urllib.error.URLError, TimeoutError, ValueError):
            return False

    def build_modelfile(
        self,
        *,
        base_model: str,
        dataset_path: Path,
        adapter_gguf: Optional[Path] = None,
    ) -> str:
        from_ref = base_model.split(":", 1)[-1] if ":" in base_model else base_model
        examples = self._load_examples(dataset_path)
        system_lines = [
            "You are the local Termit orchestrator runtime for this repository.",
            "Follow project rules and conventions; cite file paths; prefer verifiable, actionable steps.",
            "Do not present yourself as a separate general-purpose AI product.",
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
        lines = [
            f"FROM {from_ref}",
            "PARAMETER temperature 0.2",
            "PARAMETER num_ctx 8192",
        ]
        resolved_adapter = adapter_gguf or self._adapter_from_dataset_hint(dataset_path)
        if resolved_adapter is not None:
            lines.append(f"ADAPTER {resolved_adapter}")
        lines.append(f'SYSTEM """{system_block}"""')
        lines.append("")
        return "\n".join(lines)

    def _adapter_from_dataset_hint(self, dataset_path: Path) -> Optional[Path]:
        stem = dataset_path.stem.split("_")[0]
        for candidate in (
            self.adapters_dir / stem / "adapter.gguf",
            self.adapters_dir / f"{stem}.gguf",
        ):
            if candidate.exists():
                return candidate.resolve()
        return None

    def _load_examples(self, dataset_path: Path) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for line in dataset_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            messages = item.get("messages")
            if isinstance(messages, list) and messages:
                instruction = ""
                output = ""
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    role = str(message.get("role", ""))
                    content = str(message.get("content", "")).strip()
                    if role == "user" and not instruction:
                        instruction = content
                    if role == "assistant":
                        output = content
                rows.append({"instruction": instruction, "output": output})
            else:
                rows.append(
                    {
                        "instruction": str(item.get("instruction", "")),
                        "output": str(item.get("output", "")),
                    }
                )
            if len(rows) >= self.max_prompt_examples:
                break
        return rows
