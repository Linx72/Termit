from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4

from app.services.mcp_stdio_client import McpStdioSession, McpToolDescriptor


def _slug_server_id(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug or f"mcp_{uuid4().hex[:8]}"


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
        self._sessions: dict[str, McpStdioSession] = {}
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

    def import_from_mcp_file(self, source_path: Path, *, merge: bool = True) -> list[McpServerRecord]:
        """Import servers from Termit registry JSON or Cursor ``.cursor/mcp.json``."""
        path = source_path.expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"MCP config not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        incoming = self._parse_raw_items(raw)
        if not incoming:
            return []
        if not merge:
            records = incoming
            self._save(records)
            return records
        records = self._load()
        by_id = {item.server_id: item for item in records}
        for item in incoming:
            by_id[item.server_id] = item
        merged = list(by_id.values())
        self._save(merged)
        return incoming

    def sync_cursor_mcp(self, workspace_root: str) -> list[McpServerRecord]:
        root = Path(workspace_root).expanduser().resolve()
        return self.import_from_mcp_file(root / ".cursor" / "mcp.json", merge=True)

    def close_sessions(self) -> None:
        with self._lock:
            for session in self._sessions.values():
                try:
                    session.close()
                except OSError:
                    pass
            self._sessions.clear()

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
        if self._prefers_one_shot_transport(server):
            return self._invoke_stdio_json(server, tool_name, arguments)
        try:
            return self._invoke_stdio_session(server, tool_name, arguments)
        except (RuntimeError, TimeoutError, OSError, ValueError) as exc:
            self._drop_session(server.server_id)
            return self._invoke_stdio_json(server, tool_name, arguments, fallback_error=str(exc))

    @staticmethod
    def _prefers_one_shot_transport(server: McpServerRecord) -> bool:
        joined = " ".join([server.command, *server.args]).lower()
        return "-c" in joined or server.command.strip().lower() == "echo"

    def _drop_session(self, server_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(server_id, None)
        if session is not None:
            try:
                session.close()
            except OSError:
                pass

    def list_tools(self, server_id: str) -> list[McpToolDescriptor]:
        server = self.get_server(server_id)
        if server is None or not server.enabled:
            raise ValueError(f"MCP server not found or disabled: {server_id}")
        if server.command.strip().lower() in {"", "stub"}:
            return [McpToolDescriptor(name="stub_ping", description="Stub MCP tool")]
        session = self._get_session(server)
        return session.list_tools()

    def ping_server(self, server_id: str) -> bool:
        server = self.get_server(server_id)
        if server is None or not server.enabled:
            raise ValueError(f"MCP server not found or disabled: {server_id}")
        if server.command.strip().lower() in {"", "stub"}:
            return True
        session = self._get_session(server)
        return session.ping()

    def list_resources(self, server_id: str):
        from app.services.mcp_stdio_client import McpResourceDescriptor

        server = self.get_server(server_id)
        if server is None or not server.enabled:
            raise ValueError(f"MCP server not found or disabled: {server_id}")
        if server.command.strip().lower() in {"", "stub"}:
            return []
        session = self._get_session(server)
        return session.list_resources()

    def list_prompts(self, server_id: str):
        from app.services.mcp_stdio_client import McpPromptDescriptor

        server = self.get_server(server_id)
        if server is None or not server.enabled:
            raise ValueError(f"MCP server not found or disabled: {server_id}")
        if server.command.strip().lower() in {"", "stub"}:
            return []
        session = self._get_session(server)
        return session.list_prompts()

    def read_resource(self, server_id: str, uri: str) -> dict[str, object]:
        server = self.get_server(server_id)
        if server is None or not server.enabled:
            raise ValueError(f"MCP server not found or disabled: {server_id}")
        if server.command.strip().lower() in {"", "stub"}:
            return {"contents": [{"uri": uri, "text": "stub resource"}]}
        session = self._get_session(server)
        return session.read_resource(uri)

    def get_prompt(
        self,
        server_id: str,
        name: str,
        arguments: dict[str, object] | None = None,
    ) -> dict[str, object]:
        server = self.get_server(server_id)
        if server is None or not server.enabled:
            raise ValueError(f"MCP server not found or disabled: {server_id}")
        if server.command.strip().lower() in {"", "stub"}:
            return {"description": "stub prompt", "messages": [{"role": "user", "content": {"type": "text", "text": name}}]}
        session = self._get_session(server)
        return session.get_prompt(name, arguments or {})

    def get_capabilities(self, server_id: str) -> dict[str, object]:
        server = self.get_server(server_id)
        if server is None:
            raise ValueError(f"MCP server not found: {server_id}")
        if not server.enabled:
            return {
                "server_id": server_id,
                "enabled": False,
                "ping_ok": False,
                "tools_count": 0,
                "resources_count": 0,
                "prompts_count": 0,
                "transport": "disabled",
            }
        if server.command.strip().lower() in {"", "stub"}:
            return {
                "server_id": server_id,
                "enabled": True,
                "ping_ok": True,
                "tools_count": 1,
                "resources_count": 0,
                "prompts_count": 0,
                "transport": "stub",
            }
        session = self._get_session(server)
        ping_ok = session.ping()
        tools = session.list_tools()
        resources = session.list_resources()
        prompts = session.list_prompts()
        return {
            "server_id": server_id,
            "enabled": True,
            "ping_ok": ping_ok,
            "tools_count": len(tools),
            "resources_count": len(resources),
            "prompts_count": len(prompts),
            "transport": "stdio_session",
        }

    def _get_session(self, server: McpServerRecord) -> McpStdioSession:
        with self._lock:
            session = self._sessions.get(server.server_id)
            if session is None:
                session = McpStdioSession(command=server.command, args=server.args)
                self._sessions[server.server_id] = session
            else:
                session.start()
            return session

    def _invoke_stdio_session(
        self,
        server: McpServerRecord,
        tool_name: str,
        arguments: dict[str, object],
    ) -> str:
        session = self._get_session(server)
        result = session.call_tool(tool_name, arguments)
        payload = {
            "server_id": server.server_id,
            "tool": tool_name,
            "arguments": arguments,
            "status": "ok",
            "transport": "stdio_session",
            "result": result,
        }
        encoded = json.dumps(payload, ensure_ascii=True)
        self._audit(server.server_id, tool_name, arguments, encoded, transport="stdio_session")
        return encoded

    def _invoke_stdio_json(
        self,
        server: McpServerRecord,
        tool_name: str,
        arguments: dict[str, object],
        *,
        fallback_error: str | None = None,
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
            if fallback_error:
                payload["session_fallback"] = fallback_error
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
        return self._parse_raw_items(raw)

    @staticmethod
    def _parse_raw_items(raw: object) -> list[McpServerRecord]:
        items: list[dict[str, object]] = []
        if isinstance(raw, list):
            items = [item for item in raw if isinstance(item, dict)]
        elif isinstance(raw, dict):
            servers = raw.get("servers")
            if isinstance(servers, list):
                items = [item for item in servers if isinstance(item, dict)]
            else:
                cursor_servers = raw.get("mcpServers")
                if isinstance(cursor_servers, dict):
                    for key, cfg in cursor_servers.items():
                        if not isinstance(cfg, dict):
                            continue
                        items.append(
                            {
                                "server_id": _slug_server_id(str(key)),
                                "name": str(key),
                                "command": cfg.get("command", ""),
                                "args": cfg.get("args", []),
                                "enabled": not bool(cfg.get("disabled", False)),
                            }
                        )
        records: list[McpServerRecord] = []
        for item in items:
            record = McpRegistryService._record_from_dict(item)
            if record is not None:
                records.append(record)
        return records

    @staticmethod
    def _record_from_dict(item: dict[str, object]) -> Optional[McpServerRecord]:
        name = str(item.get("name") or "").strip()
        server_id = str(item.get("server_id") or item.get("id") or "").strip()
        if not server_id and name:
            server_id = _slug_server_id(name)
        if not server_id:
            return None
        command = str(item.get("command") or "")
        args_raw = item.get("args", [])
        args = [str(arg) for arg in args_raw] if isinstance(args_raw, list) else []
        allowed_raw = item.get("allowed_tools")
        allowed_tools = (
            [str(tool) for tool in allowed_raw]
            if isinstance(allowed_raw, list)
            else None
        )
        return McpServerRecord(
            server_id=server_id,
            name=name or server_id,
            command=command,
            args=args,
            enabled=bool(item.get("enabled", True)),
            allowed_tools=allowed_tools,
        )

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
