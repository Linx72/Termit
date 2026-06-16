#!/usr/bin/env python3
"""MCP stdio server — Playwright browser tools for Termit agent loop (opt-in).

Expose browser_navigate, browser_snapshot, browser_click via MCP so agents can use
mcp_invoke(server_id=termit-browser) instead of native loop tools.

Requires: pip install playwright && playwright install chromium
Enable server in data/mcp_servers.json (set enabled=true) or Desktop MCP settings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.playwright_browser_service import (  # noqa: E402
    PlaywrightBrowserService,
    PlaywrightUnavailableError,
)

_BROWSER = PlaywrightBrowserService()

_TOOLS = [
    {
        "name": "browser_navigate",
        "description": "Open URL in headless Chromium (Playwright). Returns title and text excerpt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL"},
                "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 120},
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_snapshot",
        "description": "Return current page title and text excerpt from active browser session.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "browser_click",
        "description": "Click CSS selector. Requires confirmed=true (human approval).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["selector"],
        },
    },
]


def _read_message() -> dict[str, object] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        decoded = line.decode("utf-8", errors="replace").strip()
        if decoded == "":
            break
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length_raw = headers.get("content-length")
    if not length_raw:
        return None
    body = sys.stdin.buffer.read(int(length_raw))
    if not body:
        return None
    parsed = json.loads(body.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _write_message(payload: dict[str, object]) -> None:
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _dispatch_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
    if not _BROWSER.available():
        raise PlaywrightUnavailableError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )
    if name == "browser_navigate":
        return _BROWSER.navigate(
            str(arguments.get("url", "")),
            timeout_seconds=int(arguments.get("timeout_seconds", 30)),
        )
    if name == "browser_snapshot":
        return _BROWSER.snapshot()
    if name == "browser_click":
        return _BROWSER.click(
            str(arguments.get("selector", "")),
            confirmed=bool(arguments.get("confirmed", False)),
        )
    raise ValueError(f"Unknown tool: {name}")


def _handle_call(params: dict[str, object]) -> dict[str, object]:
    tool_name = str(params.get("name", "")).strip()
    raw_args = params.get("arguments", {})
    arguments = raw_args if isinstance(raw_args, dict) else {}
    try:
        payload = _dispatch_tool(tool_name, arguments)
        text = json.dumps(payload, ensure_ascii=True)
    except Exception as exc:  # noqa: BLE001 — MCP tool errors return as JSON text
        text = json.dumps({"error": str(exc), "tool": tool_name}, ensure_ascii=True)
    return {"content": [{"type": "text", "text": text}]}


def main() -> None:
    while True:
        message = _read_message()
        if message is None:
            break
        method = message.get("method")
        req_id = message.get("id")
        if method == "initialize":
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "termit-browser", "version": "0.4.7"},
                    },
                }
            )
        elif method == "tools/list":
            _write_message({"jsonrpc": "2.0", "id": req_id, "result": {"tools": _TOOLS}})
        elif method == "tools/call" and req_id is not None:
            params = message.get("params", {})
            params_dict = params if isinstance(params, dict) else {}
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": _handle_call(params_dict),
                }
            )


if __name__ == "__main__":
    main()
