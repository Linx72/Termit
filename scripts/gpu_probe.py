#!/usr/bin/env python3
"""Probe local GPU availability for HF DPO training."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def _probe_remote_gpu(ssh_target: str) -> dict[str, object] | None:
    """Проб GPU на удалённом хосте через SSH (TERMIT_REMOTE_GPU_SSH)."""
    if not ssh_target.strip():
        return None
    try:
        completed = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                ssh_target.strip(),
                "python3",
                "-c",
                "import json,shutil,subprocess;"
                "out={'gpu_available':False,'backend':'remote','devices':[]};"
                "import shutil as s;"
                "if s.which('nvidia-smi'):"
                " p=subprocess.run(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],"
                " capture_output=True,text=True,timeout=10);"
                " if p.returncode==0 and p.stdout.strip():"
                "  out={'gpu_available':True,'backend':'remote-nvidia-smi',"
                " 'devices':[l.strip() for l in p.stdout.splitlines() if l.strip()]};"
                "print(json.dumps(out))",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
            if isinstance(payload, dict):
                payload["remote_ssh"] = ssh_target.strip()
                return payload
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


def probe_gpu() -> dict[str, object]:
    remote_ssh = __import__("os").getenv("TERMIT_REMOTE_GPU_SSH", "").strip()
    if remote_ssh:
        remote = _probe_remote_gpu(remote_ssh)
        if remote is not None:
            return remote

    if shutil.which("nvidia-smi"):
        try:
            completed = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                names = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
                return {
                    "gpu_available": True,
                    "backend": "nvidia-smi",
                    "devices": names,
                }
        except (OSError, subprocess.TimeoutExpired):
            pass

    try:
        import torch  # type: ignore[import-not-found]

        if bool(torch.cuda.is_available()):
            count = int(torch.cuda.device_count())
            devices = [str(torch.cuda.get_device_name(index)) for index in range(count)]
            return {
                "gpu_available": True,
                "backend": "torch.cuda",
                "devices": devices,
            }
    except ImportError:
        pass

    return {
        "gpu_available": False,
        "backend": "none",
        "devices": [],
        "detail": "No NVIDIA GPU detected (nvidia-smi/torch.cuda).",
    }


def main() -> int:
    print(json.dumps(probe_gpu(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
