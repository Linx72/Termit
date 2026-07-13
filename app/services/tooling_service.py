from __future__ import annotations

import shlex
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.domain.schemas import (
    ApplyPatchHunk,
    ApplyPatchRequest,
    ApplyPatchResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ListFilesRequest,
    ListFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
    ToolAuditEvent,
    ToolRiskLevel,
)
from app.services.agent_activity_events import count_line_diff


class ToolingError(Exception):
    pass


class ToolingService:
    def __init__(
        self,
        root_path: str = ".",
        on_file_changed: Callable[[str], None] | None = None,
    ) -> None:
        self.root = Path(root_path).resolve()
        self._on_file_changed = on_file_changed
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

        files = []
        for path in sorted(target.rglob(payload.pattern)):
            if not path.is_file():
                continue
            try:
                rel = str(path.relative_to(self.root))
            except ValueError:
                rel = str(path)
            files.append(rel)
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

    def apply_patch(self, payload: ApplyPatchRequest) -> ApplyPatchResponse:
        target = self._resolve_in_root(payload.path)
        rel_path = payload.path.replace("\\", "/")

        risk_level, reason = self._classify_patch_path(rel_path)
        if risk_level == ToolRiskLevel.blocked:
            self._record_audit(
                tool_name="apply_patch",
                action="policy_block",
                risk_level=risk_level,
                allowed=False,
                reason=reason,
                path=payload.path,
            )
            return ApplyPatchResponse(
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                applied=False,
            )

        if target.exists() and not target.is_file():
            raise ToolingError(f"Path is not a file: {payload.path}")

        file_exists = target.exists()
        if not file_exists and not payload.create:
            raise ToolingError(
                f"File does not exist: {payload.path}. Set create=true to create it."
            )

        if payload.content is not None and payload.hunks:
            raise ToolingError("Provide either content or hunks, not both.")

        if payload.content is None and not payload.hunks:
            raise ToolingError("Patch must include content or at least one hunk.")

        current_text = target.read_text(encoding="utf-8") if file_exists else ""
        new_text, hunks_applied = self._build_patched_text(
            current_text=current_text,
            content=payload.content,
            hunks=payload.hunks,
        )
        preview_excerpt = new_text[:500]
        created = not file_exists
        lines_added, lines_removed = count_line_diff(current_text, new_text)

        if payload.dry_run:
            self._record_audit(
                tool_name="apply_patch",
                action="dry_run",
                risk_level=ToolRiskLevel.safe,
                allowed=True,
                reason="Dry run requested; patch was not applied.",
                path=payload.path,
            )
            return ApplyPatchResponse(
                path=payload.path,
                risk_level=ToolRiskLevel.safe,
                policy_reason="Dry run preview only.",
                applied=False,
                created=created,
                hunks_applied=hunks_applied,
                bytes_written=len(new_text.encode("utf-8")),
                preview_excerpt=preview_excerpt,
                lines_added=lines_added,
                lines_removed=lines_removed,
            )

        if not payload.confirmed:
            self._record_audit(
                tool_name="apply_patch",
                action="confirmation_required",
                risk_level=ToolRiskLevel.confirm,
                allowed=False,
                reason="File writes require explicit confirmation.",
                path=payload.path,
            )
            return ApplyPatchResponse(
                path=payload.path,
                risk_level=ToolRiskLevel.confirm,
                policy_reason="File writes require explicit confirmation.",
                applied=False,
                requires_confirmation=True,
                created=created,
                hunks_applied=hunks_applied,
                bytes_written=len(new_text.encode("utf-8")),
                preview_excerpt=preview_excerpt,
                lines_added=lines_added,
                lines_removed=lines_removed,
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_text, encoding="utf-8")
        self._record_audit(
            tool_name="apply_patch",
            action="applied",
            risk_level=ToolRiskLevel.confirm,
            allowed=True,
            reason="Patch applied.",
            path=payload.path,
        )
        if self._on_file_changed is not None:
            try:
                self._on_file_changed(rel_path)
            except Exception:  # noqa: BLE001
                pass
        return ApplyPatchResponse(
            path=payload.path,
            risk_level=ToolRiskLevel.confirm,
            policy_reason=reason,
            applied=True,
            created=created,
            hunks_applied=hunks_applied,
            bytes_written=len(new_text.encode("utf-8")),
            preview_excerpt=preview_excerpt,
            lines_added=lines_added,
            lines_removed=lines_removed,
        )

    def get_audit_events(self, limit: int = 100) -> list[ToolAuditEvent]:
        safe_limit = max(1, min(limit, 1000))
        with self._audit_lock:
            return list(self._audit_events[-safe_limit:])

    # ── Упрощённые хелперы для chat_stream tool loop ──

    def list_files_by_pattern(self, *, path: str = ".", pattern: str = "*") -> dict:
        """Список файлов по паттерну — возвращает dict для JSON-сериализации."""
        from app.domain.schemas import ListFilesRequest

        try:
            result = self.list_files(ListFilesRequest(path=path, pattern=pattern))
            return {"root": result.root, "path": result.path, "files": result.files, "count": len(result.files)}
        except ToolingError as e:
            return {"error": str(e), "path": path}

    def read_file_content(self, *, path: str = ".", file_name: str = "") -> dict:
        """Прочитать файл — возвращает dict для JSON-сериализации."""
        from app.domain.schemas import ReadFileRequest

        try:
            result = self.read_file(ReadFileRequest(path=path, file=file_name))
            return {
                "path": result.path,
                "content": result.content[:5000],  # Ограничение для контекста
                "truncated": result.truncated or len(result.content) > 5000,
                "size": len(result.content),
            }
        except ToolingError as e:
            return {"error": str(e), "path": f"{path}/{file_name}"}

    def execute_command_dry(self, *, command: str, path: str = ".") -> dict:
        """Выполнить команду с dry_run — возвращает dict для JSON-сериализации."""
        from app.domain.schemas import ExecuteCommandRequest

        try:
            result = self.execute_command(ExecuteCommandRequest(
                command=command, path=path, dry_run=True, confirmed=False,
            ))
            return {
                "command": result.command,
                "path": result.path,
                "risk_level": result.risk_level.value if result.risk_level else "unknown",
                "executed": result.executed,
                "requires_confirmation": result.requires_confirmation,
                "exit_code": result.exit_code if result.executed else None,
                "stdout": (result.stdout or "")[:3000] if result.executed else None,
                "stderr": (result.stderr or "")[:1000] if result.executed else None,
            }
        except ToolingError as e:
            return {"error": str(e), "command": command}

    def apply_patch_dry(self, *, path: str, content: str = "", hunks: list | None = None) -> dict:
        """Применить патч с dry_run — возвращает dict для JSON-сериализации."""
        from app.domain.schemas import ApplyPatchRequest, ApplyPatchHunk

        try:
            parsed_hunks = []
            if hunks:
                for h in hunks:
                    if isinstance(h, dict):
                        parsed_hunks.append(ApplyPatchHunk(
                            old_text=h.get("old_text", ""),
                            new_text=h.get("new_text", ""),
                        ))
            result = self.apply_patch(ApplyPatchRequest(
                path=path,
                content=content if content else None,
                hunks=parsed_hunks if parsed_hunks else None,
                dry_run=True,
                confirmed=False,
                create=True,
            ))
            return {
                "path": result.path,
                "risk_level": result.risk_level.value if result.risk_level else "unknown",
                "applied": result.applied,
                "created": result.created,
                "bytes_written": result.bytes_written,
                "lines_added": result.lines_added,
                "lines_removed": result.lines_removed,
                "preview": result.preview_excerpt[:500] if result.preview_excerpt else "",
            }
        except ToolingError as e:
            return {"error": str(e), "path": path}

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
            "cp",
            "mv",
            "mkdir",
            "touch",
            "rmdir",
            "ln",
            "git",
            "npm",
            "npx",
            "yarn",
            "make",
            "curl",
            "wget",
            "pip",
            "pip3",
            "poetry",
            "ruff",
            "black",
            "mypy",
            "go",
            "cargo",
            "node",
            "tsc",
            "eslint",
            "prettier",
            "tail",
            "head",
            "wc",
            "find",
            "grep",
            "egrep",
            "fgrep",
            "sed",
            "awk",
            "gawk",
            "sort",
            "uniq",
            "cut",
            "tr",
            "docker",
            "ps",
            "df",
            "du",
            "env",
            "printenv",
            "id",
            "uname",
            "hostname",
            "file",
            "stat",
            "readlink",
            "basename",
            "dirname",
            "realpath",
            "tar",
            "gzip",
            "gunzip",
            "zip",
            "unzip",
            "diff",
            "patch",
            "xargs",
            "tee",
            "jq",
            "sqlite3",
            "openssl",
            "ssh-keygen",
            "pg_isready",
            "redis-cli",
        }
        if command in safe:
            return ToolRiskLevel.safe, "Command is allowlisted as safe."

        return ToolRiskLevel.confirm, "Command is not allowlisted and needs confirmation."

    def _classify_patch_path(self, rel_path: str) -> tuple[ToolRiskLevel, str]:
        normalized = rel_path.replace("\\", "/").strip("/")
        lower = normalized.lower()
        basename = Path(normalized).name.lower()

        blocked_prefixes = (".git/", ".ssh/")
        blocked_exact = {".env", ".env.local", ".env.production", "credentials.json"}
        blocked_suffixes = (".pem", ".key", ".p12", ".pfx")

        if lower in blocked_exact or basename in blocked_exact:
            return ToolRiskLevel.blocked, "Path is blocked by safety policy."
        if any(lower.startswith(prefix) or f"/{prefix}" in f"/{lower}/" for prefix in blocked_prefixes):
            return ToolRiskLevel.blocked, "Path is blocked by safety policy."
        if lower.endswith(blocked_suffixes) or basename.endswith(blocked_suffixes):
            return ToolRiskLevel.blocked, "Path is blocked by safety policy."

        return ToolRiskLevel.confirm, "File write requires confirmation."

    @staticmethod
    def _build_patched_text(
        *,
        current_text: str,
        content: str | None,
        hunks: list[ApplyPatchHunk],
    ) -> tuple[str, int]:
        if content is not None:
            return content, 0

        updated = current_text
        for index, hunk in enumerate(hunks):
            count = updated.count(hunk.old_text)
            if count == 0:
                raise ToolingError(f"Hunk {index + 1} old_text not found in file.")
            if count > 1:
                raise ToolingError(f"Hunk {index + 1} old_text matches {count} times; must be unique.")
            updated = updated.replace(hunk.old_text, hunk.new_text, 1)
        return updated, len(hunks)

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
