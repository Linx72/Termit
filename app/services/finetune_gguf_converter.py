from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class GgufConvertResult:
    status: str
    gguf_path: Optional[str] = None
    command: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "gguf_path": self.gguf_path,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "detail": self.detail,
        }


def _find_convert_script(llama_cpp_path: Optional[str] = None) -> Optional[Path]:
    candidates: list[Path] = []
    if llama_cpp_path:
        root = Path(llama_cpp_path).expanduser()
        candidates.extend(
            [
                root / "convert_lora_to_gguf.py",
                root / "examples" / "convert_lora_to_gguf.py",
                root / "tools" / "convert_lora_to_gguf.py",
            ]
        )
    env_path = os.getenv("LLAMA_CPP_PATH", "").strip()
    if env_path:
        root = Path(env_path).expanduser()
        candidates.extend(
            [
                root / "convert_lora_to_gguf.py",
                root / "examples" / "convert_lora_to_gguf.py",
            ]
        )
    which = shutil.which("convert_lora_to_gguf.py")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.exists() and path.is_file():
            return path.resolve()
    return None


def convert_adapter_to_gguf(
    *,
    adapter_dir: Path,
    output_gguf: Path,
    base_model: str,
    llama_cpp_path: Optional[str] = None,
    timeout_seconds: int = 600,
) -> GgufConvertResult:
    adapter_dir = adapter_dir.resolve()
    output_gguf = output_gguf.resolve()
    output_gguf.parent.mkdir(parents=True, exist_ok=True)

    if output_gguf.exists() and output_gguf.stat().st_size > 0:
        return GgufConvertResult(
            status="completed",
            gguf_path=str(output_gguf),
            detail="GGUF adapter already exists.",
        )

    if not adapter_dir.exists():
        return GgufConvertResult(
            status="failed",
            detail=f"Adapter directory not found: {adapter_dir}",
        )

    has_peft = (adapter_dir / "adapter_config.json").exists() or (
        adapter_dir / "adapter_model.safetensors"
    ).exists()
    if not has_peft:
        return GgufConvertResult(
            status="skipped",
            detail=f"No PEFT adapter artifacts in {adapter_dir}",
        )

    script = _find_convert_script(llama_cpp_path)
    if script is None:
        return GgufConvertResult(
            status="skipped",
            detail=(
                "llama.cpp convert_lora_to_gguf.py not found. "
                "Set LLAMA_CPP_PATH or install llama.cpp."
            ),
        )

    command = [
        sys.executable,
        str(script),
        "--outfile",
        str(output_gguf),
        "--outtype",
        "f16",
        str(adapter_dir),
    ]
    if base_model.strip():
        command.extend(["--base", base_model.strip()])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(30, timeout_seconds),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return GgufConvertResult(
            status="failed",
            command=" ".join(command),
            stdout=(exc.stdout or "")[:2000] if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "")[:2000] if isinstance(exc.stderr, str) else "",
            detail=f"GGUF conversion timed out after {timeout_seconds}s",
        )

    ok = completed.returncode == 0 and output_gguf.exists()
    return GgufConvertResult(
        status="completed" if ok else "failed",
        gguf_path=str(output_gguf) if ok else None,
        command=" ".join(command),
        stdout=(completed.stdout or "")[:2000],
        stderr=(completed.stderr or "")[:2000],
        detail="GGUF adapter converted." if ok else f"convert exit {completed.returncode}",
    )


def write_convert_manifest(adapter_dir: Path, result: GgufConvertResult) -> Path:
    manifest_path = adapter_dir / "termit_gguf_manifest.json"
    payload = result.to_dict()
    payload["adapter_dir"] = str(adapter_dir)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path
