#!/usr/bin/env python3
"""Probe local GPU availability for HF DPO training."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def probe_gpu() -> dict[str, object]:
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
