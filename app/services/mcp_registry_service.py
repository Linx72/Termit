from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4


@dataclass
class McpServerRecord:
    server_id: str
    name: str
    command: str
    args: list[str]
    enabled: bool = True
    allowed_tools: list[str] | None = None


class McpRegistryService:
    def __init__(self, file_path: str, *, audit_path: str | None = None) -> None:
        self.file_path = Path(file_path)
        self.audit_path = Path(audit_path or self.file_path.with_name("mcp_audit.jsonl"))
        self._lock = Lock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.is_file():
            self._save([])

    def list_servers(self) -> list[McpServerRecord]:
        return self._load()

    def get_server(self, server_id: str) -> Optional[McpServerRecord]:
        for item in self._load():
            if item.server_id == server_id:
                return item
        return None

    def upsert_server(
        self,
        *,
        name: str,
        command: str,
        args: list[str] | None = None,
        enabled: bool = True,
        allowed_tools: list[str] | None = None,
        server_id: str | None = None,
    ) -> McpServerRecord:
        records = self._load()
        sid = server_id or f"mcp_{uuid4().hex[:10]}"
        record = McpServerRecord(
            server_id=sid,
            name=name,
            command=command,
            args=args or [],
            enabled=enabled,
            allowed_tools=allowed_tools,
        )
        replaced = False
        for index, item in enumerate(records):
            if item.server_id == sid:
                records[index] = record
                replaced = True
                break
        if not replaced:
            records.append(record)
        self._save(records)
        return record

    def invoke_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> str:
        server = self.get_server(server_id)
        if server is None or not server.enabled:
            raise ValueError(f"MCP server not found or disabled: {server_id}")
        if server.allowed_tools and tool_name not in server.allowed_tools:
            raise ValueError(f"Tool {tool_name!r} not allowed on server {server_id}")
        if server.command.strip().lower() in {"", "stub"}:
            payload = {
                "server_id": server_id,
                "tool": tool_name,
                "arguments": arguments,
                "status": "stub_ok",
                "detail": "MCP stub server — set a real command to use stdio_json transport.",
            }
            result = json.dumps(payload, ensure_ascii=True)
            self._audit(server_id, tool_name, arguments, result, transport="stub")
            return result
        return self._invoke_stdio_json(server, tool_name, arguments)

    def _invoke_stdio_json(
        self,
        server: McpServerRecord,
        tool_name: str,
        arguments: dict[str, object],
    ) -> str:
        request_payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
            ensure_ascii=True,
        )
        try:
            completed = subprocess.run(
                [server.command, *server.args],
                input=request_payload,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            payload = {
                "server_id": server.server_id,
                "tool": tool_name,
                "status": "transport_error",
                "error": str(exc),
            }
            result = json.dumps(payload, ensure_ascii=True)
            self._audit(server.server_id, tool_name, arguments, result, transport="stdio_json")
            return result
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0 and not stdout:
            payload = {
                "server_id": server.server_id,
                "tool": tool_name,
                "status": "process_error",
                "exit_code": completed.returncode,
                "stderr": stderr[:2000],
            }
            result = json.dumps(payload, ensure_ascii=True)
            self._audit(server.server_id, tool_name, arguments, result, transport="stdio_json")
            return result
        if stdout:
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, dict):
                    parsed.setdefault("server_id", server.server_id)
                    parsed.setdefault("tool", tool_name)
                    parsed.setdefault("status", "ok")
                    result = json.dumps(parsed, ensure_ascii=True)
                    self._audit(server.server_id, tool_name, arguments, result, transport="stdio_json")
                    return result
            except json.JSONDecodeError:
                pass
        payload = {
            "server_id": server.server_id,
            "tool": tool_name,
            "status": "ok",
            "stdout": stdout[:4000],
            "stderr": stderr[:1000],
        }
        result = json.dumps(payload, ensure_ascii=True)
        self._audit(server.server_id, tool_name, arguments, result, transport="stdio_json")
        return result

    def _audit(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, object],
        result: str,
        *,
        transport: str,
    ) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_id": server_id,
            "tool": tool_name,
            "arguments": arguments,
            "transport": transport,
            "result_preview": result[:500],
        }
        with self._lock:
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    def _load(self) -> list[McpServerRecord]:
        if not self.file_path.is_file():
            return []
        raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        records: list[McpServerRecord] = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            records.append(
                McpServerRecord(
                    server_id=str(item.get("server_id", "")),
                    name=str(item.get("name", "")),
                    command=str(item.get("command", "")),
                    args=[str(arg) for arg in item.get("args", [])],
                    enabled=bool(item.get("enabled", True)),
                    allowed_tools=item.get("allowed_tools"),
                )
            )
        return records

    def _save(self, records: list[McpServerRecord]) -> None:
        payload = [
            {
                "server_id": item.server_id,
                "name": item.name,
                "command": item.command,
                "args": item.args,
                "enabled": item.enabled,
                "allowed_tools": item.allowed_tools,
            }
            for item in records
        ]
        with self._lock:
            self.file_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
