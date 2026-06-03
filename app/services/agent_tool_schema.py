from __future__ import annotations

TOOL_DEFINITIONS: dict[str, dict[str, object]] = {
    "list_files": {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path relative to workspace root."},
                    "pattern": {"type": "string", "description": "Glob pattern, default *."},
                },
                "required": ["path"],
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory containing the file."},
                    "file": {"type": "string", "description": "File name or relative path."},
                },
                "required": ["path", "file"],
            },
        },
    },
    "execute_command": {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "path": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["command"],
            },
        },
    },
    "apply_patch": {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a file patch in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "hunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_text": {"type": "string"},
                                "new_text": {"type": "string"},
                            },
                            "required": ["old_text", "new_text"],
                        },
                    },
                    "create": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["path"],
            },
        },
    },
    "web_automation": {
        "type": "function",
        "function": {
            "name": "web_automation",
            "description": "Fetch web page evidence for an online objective.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "objective": {"type": "string"},
                    "max_steps": {"type": "integer"},
                },
                "required": ["url", "objective"],
            },
        },
    },
    "browser_navigate": {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Open a URL in the headless browser (Playwright when enabled).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["url"],
            },
        },
    },
    "browser_snapshot": {
        "type": "function",
        "function": {
            "name": "browser_snapshot",
            "description": "Return title and text excerpt from the active browser session.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "browser_click": {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element by CSS selector (requires confirmed=true).",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["selector"],
            },
        },
    },
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return structured ranked results with citations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional domain allow-list filter.",
                    },
                    "recency_days": {
                        "type": "integer",
                        "description": "Optional recency window in days.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "spawn_agent": {
        "type": "function",
        "function": {
            "name": "spawn_agent",
            "description": "Spawn a child agent run and return its summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "task": {"type": "string"},
                },
                "required": ["task"],
            },
        },
    },
    "mcp_invoke": {
        "type": "function",
        "function": {
            "name": "mcp_invoke",
            "description": "Invoke a tool on a registered MCP server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["server_id", "tool_name"],
            },
        },
    },
}


def build_openai_tools(enabled_tools: list[str]) -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    for name in enabled_tools:
        spec = TOOL_DEFINITIONS.get(name)
        if spec is not None:
            tools.append(spec)
    return tools
