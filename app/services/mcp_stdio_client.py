from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class McpToolDescriptor:
    name: str
    description: str = ""
    input_schema: dict[str, object] = field(default_factory=dict)


class McpStdioSession:
    """Minimal MCP stdio client: initialize → tools/list → tools/call."""

    def __init__(
        self,
        *,
        command: str,
        args: list[str],
        client_name: str = "termit",
        client_version: str = "0.3.2",
        timeout_seconds: int = 30,
    ) -> None:
        self._command = command
        self._args = args
        self._client_name = client_name
        self._client_version = client_version
        self._timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[bytes] | None = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._initialized = False
        self._tools: list[McpToolDescriptor] = []

    @property
    def tools(self) -> list[McpToolDescriptor]:
        return list(self._tools)

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._process = subprocess.Popen(
            [self._command, *self._args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._initialized = False
        self._tools = []
        self._initialize_session()

    def close(self) -> None:
        process = self._process
        self._process = None
        self._initialized = False
        self._tools = []
        if process is None:
            return
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

    def list_tools(self) -> list[McpToolDescriptor]:
        self.start()
        response = self._request("tools/list", {})
        tools_raw = response.get("tools", []) if isinstance(response, dict) else []
        self._tools = []
        if isinstance(tools_raw, list):
            for item in tools_raw:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                schema = item.get("inputSchema", item.get("input_schema", {}))
                self._tools.append(
                    McpToolDescriptor(
                        name=name,
                        description=str(item.get("description", "")),
                        input_schema=schema if isinstance(schema, dict) else {},
                    )
                )
        return self.tools

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        self.start()
        result = self._request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        return result if isinstance(result, dict) else {"content": [{"type": "text", "text": str(result)}]}

    def _initialize_session(self) -> None:
        if self._initialized:
            return
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": self._client_name, "version": self._client_version},
            },
        )
        if not isinstance(result, dict):
            raise RuntimeError("MCP initialize returned invalid payload.")
        self._send_notification("notifications/initialized", {})
        self._initialized = True
        self.list_tools()

    def _request(self, method: str, params: dict[str, object]) -> Any:
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
            self._write_message(payload)
            while True:
                message = self._read_message()
                if "id" not in message:
                    continue
                if message.get("id") == request_id:
                    if "error" in message:
                        error = message["error"]
                        detail = error.get("message", error) if isinstance(error, dict) else error
                        raise RuntimeError(f"MCP {method} failed: {detail}")
                    return message.get("result")

    def _send_notification(self, method: str, params: dict[str, object]) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self._write_message(payload)

    def _write_message(self, payload: dict[str, object]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise RuntimeError("MCP process is not running.")
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        process.stdin.write(header + data)
        process.stdin.flush()

    def _read_message(self) -> dict[str, object]:
        process = self._process
        if process is None or process.stdout is None:
            raise RuntimeError("MCP process is not running.")
        headers: dict[str, str] = {}
        while True:
            line = process.stdout.readline()
            if not line:
                raise RuntimeError("MCP process closed stdout.")
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded == "":
                break
            if ":" in decoded:
                key, value = decoded.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        length_raw = headers.get("content-length")
        if not length_raw:
            raise RuntimeError("MCP frame missing Content-Length.")
        body = process.stdout.read(int(length_raw))
        if not body:
            raise RuntimeError("MCP frame body missing.")
        parsed = json.loads(body.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {"result": parsed}
