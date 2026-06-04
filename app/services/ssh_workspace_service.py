"""Remote workspace over OpenSSH (BatchMode) for agent file/command tools."""

from __future__ import annotations

import base64
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.domain.schemas import (
    ApplyPatchRequest,
    ApplyPatchResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ListFilesRequest,
    ListFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
    ToolRiskLevel,
)
from app.services.tooling_service import ToolingError, ToolingService


@dataclass(frozen=True)
class SshWorkspaceConfig:
    host: str
    user: str
    remote_path: str
    port: int = 22
    identity_file: str = ""

    def is_valid(self) -> bool:
        return bool(self.host.strip() and self.user.strip() and self.remote_path.strip())


class SshWorkspaceError(Exception):
    pass


class SshWorkspaceService:
    """Execute list/read/patch/command on a remote directory via ``ssh`` CLI."""

    def __init__(self, local_tooling: ToolingService) -> None:
        self._local = local_tooling

    @staticmethod
    def from_run_payload(
        *,
        ssh_host: str | None,
        ssh_user: str | None,
        ssh_remote_path: str | None,
        ssh_port: int | None = None,
        ssh_identity: str | None = None,
    ) -> SshWorkspaceConfig | None:
        host = (ssh_host or "").strip()
        user = (ssh_user or "").strip()
        remote_path = (ssh_remote_path or "").strip()
        if not host or not user or not remote_path:
            return None
        return SshWorkspaceConfig(
            host=host,
            user=user,
            remote_path=remote_path,
            port=int(ssh_port or 22),
            identity_file=(ssh_identity or "").strip(),
        )

    def test_connection(self, config: SshWorkspaceConfig) -> tuple[bool, str]:
        if not config.is_valid():
            return False, "SSH host, user and remote_path are required."
        cmd = self._remote_shell(config, "pwd && test -d . && echo OK")
        completed = self._run_ssh(config, cmd, timeout_seconds=20)
        out = (completed.stdout or "").strip()
        if completed.returncode == 0 and "OK" in out:
            return True, out.splitlines()[-1] if out else "connected"
        detail = (completed.stderr or completed.stdout or "ssh failed").strip()
        return False, detail[:500]

    def list_files(self, config: SshWorkspaceConfig, payload: ListFilesRequest) -> ListFilesResponse:
        rel = payload.path.strip() or "."
        pattern = payload.pattern.strip() or "*"
        script = (
            f"cd {shlex.quote(rel)} && "
            f"find . -type f -name {shlex.quote(pattern)} 2>/dev/null | sed 's|^\\./||' | sort"
        )
        completed = self._run_ssh(config, self._remote_shell(config, script), timeout_seconds=60)
        if completed.returncode != 0:
            raise ToolingError((completed.stderr or "list_files failed")[:500])
        files = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
        return ListFilesResponse(root=config.remote_path, path=payload.path, files=files)

    def read_file(self, config: SshWorkspaceConfig, payload: ReadFileRequest) -> ReadFileResponse:
        rel = payload.path.replace("\\", "/")
        script = f"test -f {shlex.quote(rel)} && wc -c < {shlex.quote(rel)} && head -c {payload.max_bytes} {shlex.quote(rel)}"
        completed = self._run_ssh(config, self._remote_shell(config, script), timeout_seconds=30)
        if completed.returncode != 0:
            raise ToolingError(f"File does not exist or is not readable: {payload.path}")
        lines = (completed.stdout or "").split("\n", 1)
        if not lines:
            raise ToolingError(f"Empty read for: {payload.path}")
        try:
            size = int(lines[0].strip())
        except ValueError as exc:
            raise ToolingError(f"Failed to read file size: {payload.path}") from exc
        content = lines[1] if len(lines) > 1 else ""
        return ReadFileResponse(path=payload.path, content=content, truncated=size > payload.max_bytes)

    def execute_command(
        self, config: SshWorkspaceConfig, payload: ExecuteCommandRequest
    ) -> ExecuteCommandResponse:
        args = shlex.split(payload.command)
        if not args:
            raise ToolingError("Command is empty.")
        risk_level, reason = self._local._classify_command(args)  # noqa: SLF001 — reuse policy
        if risk_level == ToolRiskLevel.blocked:
            return ExecuteCommandResponse(
                command=payload.command,
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                executed=False,
            )
        if payload.dry_run:
            return ExecuteCommandResponse(
                command=payload.command,
                path=payload.path,
                risk_level=risk_level,
                policy_reason="Dry run (remote SSH).",
                executed=False,
            )
        cwd = payload.path.strip() or "."
        remote_cmd = f"cd {shlex.quote(cwd)} && {payload.command}"
        completed = self._run_ssh(
            config,
            self._remote_shell(config, remote_cmd),
            timeout_seconds=payload.timeout_seconds,
        )
        return ExecuteCommandResponse(
            command=payload.command,
            path=payload.path,
            risk_level=risk_level,
            policy_reason=reason,
            executed=True,
            exit_code=completed.returncode,
            stdout=(completed.stdout or "")[:20000],
            stderr=(completed.stderr or "")[:20000],
            duration_ms=0,
        )

    def apply_patch(self, config: SshWorkspaceConfig, payload: ApplyPatchRequest) -> ApplyPatchResponse:
        rel_path = payload.path.replace("\\", "/")
        risk_level, reason = self._local._classify_patch_path(rel_path)  # noqa: SLF001
        if risk_level == ToolRiskLevel.blocked:
            return ApplyPatchResponse(
                path=payload.path,
                risk_level=risk_level,
                policy_reason=reason,
                applied=False,
            )
        try:
            current = self.read_file(
                config,
                ReadFileRequest(path=payload.path, max_bytes=500_000),
            ).content
            file_exists = True
        except ToolingError:
            current = ""
            file_exists = False
        if not file_exists and not payload.create:
            raise ToolingError(f"Remote file does not exist: {payload.path}")

        with tempfile.TemporaryDirectory() as tmp:
            local_root = Path(tmp)
            local_tool = ToolingService(root_path=str(local_root))
            rel = Path(rel_path)
            target = local_root / rel
            if file_exists:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(current, encoding="utf-8")
            local_result = local_tool.apply_patch(payload)
            if not local_result.applied and not payload.dry_run:
                return local_result
            if payload.dry_run:
                return local_result
            if not target.exists():
                raise ToolingError(f"Patch did not produce file: {payload.path}")
            new_text = target.read_text(encoding="utf-8")
        if not payload.confirmed:
            return ApplyPatchResponse(
                path=payload.path,
                risk_level=ToolRiskLevel.confirm,
                policy_reason="Remote file writes require explicit confirmation.",
                applied=False,
                requires_confirmation=True,
                preview_excerpt=new_text[:500],
            )
        self._write_remote_text(config, rel_path, new_text)
        return ApplyPatchResponse(
            path=payload.path,
            risk_level=ToolRiskLevel.confirm,
            policy_reason="Patch applied on remote workspace.",
            applied=True,
            created=not file_exists,
            hunks_applied=local_result.hunks_applied,
            bytes_written=len(new_text.encode("utf-8")),
            preview_excerpt=new_text[:500],
        )

    def _write_remote_text(self, config: SshWorkspaceConfig, rel_path: str, content: str) -> None:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        parent = str(Path(rel_path).parent).replace("\\", "/")
        if parent and parent != ".":
            mkdir_script = f"mkdir -p {shlex.quote(parent)}"
            mk = self._run_ssh(config, self._remote_shell(config, mkdir_script), timeout_seconds=20)
            if mk.returncode != 0:
                raise ToolingError((mk.stderr or "mkdir failed")[:300])
        script = f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(rel_path)}"
        completed = self._run_ssh(config, self._remote_shell(config, script), timeout_seconds=60)
        if completed.returncode != 0:
            raise ToolingError((completed.stderr or "remote write failed")[:500])

    def _remote_shell(self, config: SshWorkspaceConfig, inner: str) -> str:
        return f"cd {shlex.quote(config.remote_path)} && {inner}"

    def _run_ssh(
        self,
        config: SshWorkspaceConfig,
        remote_command: str,
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        target = f"{config.user}@{config.host}"
        cmd: list[str] = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        if config.port and config.port != 22:
            cmd.extend(["-p", str(config.port)])
        if config.identity_file:
            cmd.extend(["-i", config.identity_file])
        cmd.extend([target, remote_command])
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max(5, timeout_seconds),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SshWorkspaceError(f"SSH timed out after {timeout_seconds}s") from exc
        except FileNotFoundError as exc:
            raise SshWorkspaceError("OpenSSH client (ssh) not found on PATH") from exc
