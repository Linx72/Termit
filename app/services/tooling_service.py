from __future__ import annotations

import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.domain.schemas import (
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ListFilesRequest,
    ListFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
    ToolAuditEvent,
    ToolRiskLevel,
)


class ToolingError(Exception):
    pass


class ToolingService:
    def __init__(self, root_path: str = ".") -> None:
        self.root = Path(root_path).resolve()
        self._audit_lock = Lock()
        self._audit_events: list[ToolAuditEvent] = []

    def _resolve_in_root(self, unsafe_path: str) -> Path:
        candidate = (self.root / unsafe_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ToolingError("Path escapes workspace root.")
        return candidate

    def list_files(self, payload: ListFilesRequest) -> ListFilesResponse:
        target = self._resolve_in_root(payload.path)
        if not target.exists():
            raise ToolingError(f"Path does not exist: {payload.path}")
        if not target.is_dir():
            raise ToolingError(f"Path is not a directory: {payload.path}")

        files = [
            str(path.relative_to(self.root))
            for path in sorted(target.rglob(payload.pattern))
            if path.is_file()
        ]
        return ListFilesResponse(root=str(self.root), path=payload.path, files=files)

    def read_file(self, payload: ReadFileRequest) -> ReadFileResponse:
        target = self._resolve_in_root(payload.path)
        if not target.exists():
            raise ToolingError(f"File does not exist: {payload.path}")
        if not target.is_file():
            raise ToolingError(f"Path is not a file: {payload.path}")

        raw = target.read_bytes()
        truncated = len(raw) > payload.max_bytes
        data = raw[: payload.max_bytes]
        content = data.decode("utf-8", errors="replace")
        return ReadFileResponse(path=payload.path, content=content, truncated=truncated)

    def execute_command(self, payload: ExecuteCommandRequest) -> ExecuteCommandResponse:
        target = self._resolve_in_root(payload.path)
        if not target.exists():
            raise ToolingError(f"Path does not exist: {payload.path}")
        if not target.is_dir():
            raise ToolingError(f"Path is not a directory: {payload.path}")

        args = shlex.split(payload.command)
        if not args:
            raise ToolingError("Command is empty.")

        risk_level, reason = self._classify_command(args)
        if risk_level == ToolRiskLevel.blocked:
            self._record_audit(
                tool_name="execute_command",
                action="policy_block",
                risk_level=risk_level,
                allowed=False,
                reason=reason,
                command=payload.command,
                path=payload.path,
            )
            return ExecuteCommandResponse(
                command=payload.command,
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                executed=False,
                stderr="Command blocked by safety policy.",
            )

        if risk_level == ToolRiskLevel.confirm and not payload.confirmed:
            self._record_audit(
                tool_name="execute_command",
                action="confirmation_required",
                risk_level=risk_level,
                allowed=False,
                reason=reason,
                command=payload.command,
                path=payload.path,
            )
            return ExecuteCommandResponse(
                command=payload.command,
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                executed=False,
                requires_confirmation=True,
                stderr="Command requires explicit confirmation.",
            )

        if payload.dry_run:
            self._record_audit(
                tool_name="execute_command",
                action="dry_run",
                risk_level=risk_level,
                allowed=True,
                reason="Dry run requested; command was not executed.",
                command=payload.command,
                path=payload.path,
            )
            return ExecuteCommandResponse(
                command=payload.command,
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                executed=False,
                duration_ms=0,
            )

        started = time.perf_counter()
        try:
            completed = subprocess.run(
                args,
                cwd=target,
                capture_output=True,
                text=True,
                timeout=payload.timeout_seconds,
                check=False,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            stdout = completed.stdout[:20000]
            stderr = completed.stderr[:20000]
            self._record_audit(
                tool_name="execute_command",
                action="executed",
                risk_level=risk_level,
                allowed=True,
                reason="Command executed.",
                command=payload.command,
                path=payload.path,
            )
            return ExecuteCommandResponse(
                command=payload.command,
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                executed=True,
                exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._record_audit(
                tool_name="execute_command",
                action="timeout",
                risk_level=risk_level,
                allowed=True,
                reason="Command timed out.",
                command=payload.command,
                path=payload.path,
            )
            return ExecuteCommandResponse(
                command=payload.command,
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                executed=True,
                exit_code=-1,
                stderr="Command timed out.",
                duration_ms=duration_ms,
            )

    def get_audit_events(self, limit: int = 100) -> list[ToolAuditEvent]:
        safe_limit = max(1, min(limit, 1000))
        with self._audit_lock:
            return list(self._audit_events[-safe_limit:])

    def _classify_command(self, args: list[str]) -> tuple[ToolRiskLevel, str]:
        command = args[0].lower()
        full_command = " ".join(args).lower()

        blocked = {
            "rm",
            "sudo",
            "reboot",
            "shutdown",
            "poweroff",
            "mkfs",
            "dd",
            "passwd",
            "chown",
            "chmod",
            "kill",
            "pkill",
            "killall",
        }
        if command in blocked or " rm -rf " in f" {full_command} ":
            return ToolRiskLevel.blocked, "Command is destructive or privileged."

        safe = {
            "ls",
            "pwd",
            "echo",
            "whoami",
            "date",
            "rg",
            "python",
            "python3",
            "pytest",
            "uvicorn",
            "cat",
        }
        if command in safe:
            return ToolRiskLevel.safe, "Command is allowlisted as safe."

        return ToolRiskLevel.confirm, "Command is not allowlisted and needs confirmation."

    def _record_audit(
        self,
        tool_name: str,
        action: str,
        risk_level: ToolRiskLevel,
        allowed: bool,
        reason: str,
        command: str | None = None,
        path: str | None = None,
    ) -> None:
        event = ToolAuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            action=action,
            risk_level=risk_level,
            allowed=allowed,
            reason=reason,
            command=command,
            path=path,
        )
        with self._audit_lock:
            self._audit_events.append(event)
