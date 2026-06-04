"""Read/write Termit .env keys for runtime automation toggles."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


def parse_bool(value: str, *, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


class EnvFileService:
    def __init__(self, env_path: Optional[str] = None) -> None:
        raw = (env_path or os.getenv("TERMIT_ENV_FILE", ".env")).strip()
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.is_file()

    def read_value(self, key: str) -> Optional[str]:
        if not self.exists():
            return None
        pattern = re.compile(rf"^{re.escape(key)}=(.*)$")
        for line in self._path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line.strip())
            if match:
                return match.group(1).strip()
        return None

    def read_bool(self, key: str, *, default: bool = False) -> bool:
        value = self.read_value(key)
        if value is None:
            return default
        cleaned = value.strip().strip('"').strip("'")
        return parse_bool(cleaned, default=default)

    def set_key(self, key: str, value: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if self.exists():
            lines = self._path.read_text(encoding="utf-8").splitlines()
        pattern = re.compile(rf"^{re.escape(key)}=")
        replaced = False
        out: list[str] = []
        for line in lines:
            if pattern.match(line.strip()):
                out.append(f"{key}={value}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            if out and out[-1].strip():
                out.append("")
            out.append(f"{key}={value}")
        self._path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
        os.environ[key] = value.strip().strip('"').strip("'")
