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
    "mcp_read_resource": {
        "type": "function",
        "function": {
            "name": "mcp_read_resource",
            "description": "Read an MCP resource URI from a registered server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {"type": "string"},
                    "uri": {"type": "string"},
                },
                "required": ["server_id", "uri"],
            },
        },
    },
    "mcp_get_prompt": {
        "type": "function",
        "function": {
            "name": "mcp_get_prompt",
            "description": "Fetch a named MCP prompt template from a registered server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {"type": "string"},
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["server_id", "name"],
            },
        },
    },
    "generate_image": {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate PNG image from prompt; saves to Media Studio asset store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "project_id": {"type": "string"},
                    "scene_id": {"type": "string"},
                    "provider": {
                        "type": "string",
                        "description": "openai, comfy (local SDXL via ComfyUI), sdxl (alias comfy), or stub",
                    },
                    "confirmed": {"type": "boolean"},
                },
                "required": ["prompt"],
            },
        },
    },
    "list_media_assets": {
        "type": "function",
        "function": {
            "name": "list_media_assets",
            "description": "List media assets for project or run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "scene_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    "vision_qa_media": {
        "type": "function",
        "function": {
            "name": "vision_qa_media",
            "description": "Score image asset against criteria (heuristic or vision).",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "criteria": {"type": "string"},
                    "min_score": {"type": "number"},
                },
                "required": ["asset_id"],
            },
        },
    },
    "estimate_media_cost": {
        "type": "function",
        "function": {
            "name": "estimate_media_cost",
            "description": "Estimate USD cost from storyboard JSON or path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "storyboard_path": {"type": "string"},
                    "storyboard": {"type": "object"},
                },
            },
        },
    },
    "tts_generate": {
        "type": "function",
        "function": {
            "name": "tts_generate",
            "description": "Generate voiceover WAV from text (OpenAI TTS or stub).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "voice_id": {"type": "string"},
                    "language": {"type": "string"},
                    "project_id": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["text"],
            },
        },
    },
    "transcribe_media": {
        "type": "function",
        "function": {
            "name": "transcribe_media",
            "description": "Transcribe audio/video asset to SRT via Whisper.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "language": {"type": "string"},
                    "project_id": {"type": "string"},
                },
                "required": ["asset_id"],
            },
        },
    },
    "compose_media": {
        "type": "function",
        "function": {
            "name": "compose_media",
            "description": "Build MP4 slideshow from timeline (image clips, optional audio/subs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timeline_path": {"type": "string"},
                    "timeline": {"type": "object"},
                    "project_id": {"type": "string"},
                    "output_name": {"type": "string"},
                    "preset": {"type": "string", "description": "youtube_16x9|reels_9x16|telegram_1x1"},
                },
            },
        },
    },
    "render_video": {
        "type": "function",
        "function": {
            "name": "render_video",
            "description": "Start I2V render job from source image asset; returns job_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "source_asset_id": {"type": "string"},
                    "scene_id": {"type": "string"},
                    "duration_sec": {"type": "number"},
                    "mode": {"type": "string"},
                    "provider": {"type": "string"},
                    "project_id": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["prompt", "source_asset_id"],
            },
        },
    },
    "wait_media_job": {
        "type": "function",
        "function": {
            "name": "wait_media_job",
            "description": "Poll media job until terminal state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "timeout_sec": {"type": "integer"},
                },
                "required": ["job_id"],
            },
        },
    },
    "export_gif": {
        "type": "function",
        "function": {
            "name": "export_gif",
            "description": "Export animated GIF from PNG asset_ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_ids": {"type": "array", "items": {"type": "string"}},
                    "project_id": {"type": "string"},
                    "fps": {"type": "integer"},
                    "width": {"type": "integer"},
                },
                "required": ["asset_ids"],
            },
        },
    },
    "export_lottie": {
        "type": "function",
        "function": {
            "name": "export_lottie",
            "description": "Export Lottie JSON animation from PNG asset_ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_ids": {"type": "array", "items": {"type": "string"}},
                    "project_id": {"type": "string"},
                    "fps": {"type": "integer"},
                    "width": {"type": "integer"},
                },
                "required": ["asset_ids"],
            },
        },
    },
    "run_storyboard": {
        "type": "function",
        "function": {
            "name": "run_storyboard",
            "description": "Studio pipeline: storyboard scenes → images/I2V → master MP4.",
            "parameters": {
                "type": "object",
                "properties": {
                    "storyboard_path": {"type": "string"},
                    "storyboard": {"type": "object"},
                    "brand_kit_id": {"type": "string"},
                    "project_id": {"type": "string"},
                    "max_scenes": {"type": "integer"},
                    "confirmed": {"type": "boolean"},
                },
            },
        },
    },
    "describe_tools": {
        "type": "function",
        "function": {
            "name": "describe_tools",
            "description": (
                "Load full JSON schemas for deferred tools before calling them. "
                "Use when you need apply_patch, execute_command, media, MCP, or other lazy tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tool names from the agent allowlist.",
                    }
                },
                "required": ["tool_names"],
            },
        },
    },
}


# Группы для lazy tool schemas (ось B harness): старт с core, расширение по heuristics/usage.
TOOL_TIER_CORE = frozenset({"list_files", "read_file", "describe_tools"})
TOOL_TIER_MUTATE = frozenset({"apply_patch", "execute_command", "browser_click"})
TOOL_TIER_BROWSER = frozenset({"browser_navigate", "browser_snapshot", "browser_click", "web_automation"})
TOOL_TIER_ONLINE = frozenset({"web_search"})
TOOL_TIER_MCP = frozenset({"mcp_invoke", "mcp_read_resource", "mcp_get_prompt"})
TOOL_TIER_AGENT = frozenset({"spawn_agent"})
TOOL_TIER_MEDIA = frozenset(
    {
        "generate_image",
        "list_media_assets",
        "vision_qa_media",
        "estimate_media_cost",
        "tts_generate",
        "transcribe_media",
        "compose_media",
        "render_video",
        "wait_media_job",
        "export_gif",
        "export_lottie",
        "run_storyboard",
    }
)

_FILE_WRITE_MARKERS = (
    "create file",
    "write file",
    "edit file",
    "modify file",
    "update file",
    "delete file",
    "apply patch",
    "apply_patch",
    "создай файл",
    "измени файл",
    "правк",
    "patch",
    "refactor",
    "implement",
    "fix bug",
    "add test",
)

_ONLINE_MARKERS = (
    "search web",
    "google",
    "internet",
    "online",
    "browser",
    "website",
    "найди в интернете",
    "поиск",
    "стать",
)

_MEDIA_MARKERS = (
    "image",
    "video",
    "storyboard",
    "lottie",
    "gif",
    "tts",
    "media",
    "изображен",
    "видео",
    "анимац",
)


def _enabled_set(enabled_tools: list[str]) -> set[str]:
    return {name.strip() for name in enabled_tools if name and name.strip()}


def select_initial_tool_names(
    enabled_tools: list[str],
    task_message: str,
    *,
    run_mode: str = "agent",
    verify_after_patch: bool = False,
) -> list[str]:
    """Минимальный набор native tool schemas для первого шага agent loop."""
    enabled = _enabled_set(enabled_tools)
    active = set(TOOL_TIER_CORE & enabled)
    msg = task_message.lower()
    plan_only = run_mode.strip().lower() == "plan"

    if not plan_only and any(marker in msg for marker in _FILE_WRITE_MARKERS):
        active |= TOOL_TIER_MUTATE & enabled
    if not plan_only and (
        verify_after_patch
        or "test" in msg
        or "pytest" in msg
        or "npm" in msg
        or "lint" in msg
        or "verify" in msg
    ):
        if "execute_command" in enabled:
            active.add("execute_command")
    if any(marker in msg for marker in _ONLINE_MARKERS):
        active |= (TOOL_TIER_ONLINE | TOOL_TIER_BROWSER) & enabled
    if any(marker in msg for marker in _MEDIA_MARKERS):
        active |= TOOL_TIER_MEDIA & enabled
    if "mcp" in msg or "mcp_invoke" in enabled:
        active |= TOOL_TIER_MCP & enabled
    if "spawn" in msg or "subagent" in msg or "parallel" in msg:
        active |= TOOL_TIER_AGENT & enabled

    if not active:
        active = set(enabled)
    return sorted(active)


def expand_tools_after_use(
    used_tool: str,
    enabled_tools: list[str],
    current_active: set[str],
    *,
    describe_request: list[str] | None = None,
) -> set[str]:
    """Расширить lazy schema после tool call или describe_tools."""
    enabled = _enabled_set(enabled_tools)
    expanded = set(current_active)
    if describe_request:
        for name in describe_request:
            if name in enabled:
                expanded.add(name)
        if "mcp_invoke" in expanded:
            expanded |= TOOL_TIER_MCP & enabled
    if used_tool in TOOL_TIER_CORE:
        expanded |= TOOL_TIER_MUTATE & enabled
    if used_tool in {"apply_patch", "execute_command"}:
        if "execute_command" in enabled:
            expanded.add("execute_command")
        if "apply_patch" in enabled:
            expanded.add("apply_patch")
    if used_tool in TOOL_TIER_BROWSER:
        expanded |= TOOL_TIER_BROWSER & enabled
    if used_tool in TOOL_TIER_MCP:
        expanded |= TOOL_TIER_MCP & enabled
    if used_tool in TOOL_TIER_MEDIA:
        expanded |= TOOL_TIER_MEDIA & enabled
    return expanded


def resolve_described_tools(arguments: dict[str, object], enabled_tools: list[str]) -> list[str]:
    """Извлечь и отфильтровать tool_names из describe_tools arguments."""
    enabled = _enabled_set(enabled_tools)
    raw = arguments.get("tool_names", [])
    if not isinstance(raw, list):
        return []
    return [str(name).strip() for name in raw if str(name).strip() in enabled]


def build_tool_schema_response(tool_names: list[str]) -> str:
    """JSON observation для describe_tools."""
    import json

    schemas = build_openai_tools(tool_names)
    return json.dumps(
        {
            "loaded_tools": tool_names,
            "schemas": schemas,
            "hint": "Schemas are now active for native tool calling on next steps.",
        },
        ensure_ascii=True,
    )


def deferred_tool_catalog(enabled_tools: list[str], active_tools: set[str]) -> str:
    """Краткий список отложенных tools для system prompt (native loop)."""
    enabled = _enabled_set(enabled_tools)
    deferred = sorted(name for name in enabled if name not in active_tools and name in TOOL_DEFINITIONS)
    if not deferred:
        return ""
    return (
        "\n\n[Lazy tools] Schemas for these tools load on demand after exploration: "
        + ", ".join(deferred)
    )


def build_openai_tools(enabled_tools: list[str]) -> list[dict[str, object]]:
    names = list(enabled_tools)
    if "mcp_invoke" in names:
        for companion in ("mcp_read_resource", "mcp_get_prompt"):
            if companion not in names:
                names.append(companion)
    tools: list[dict[str, object]] = []
    for name in names:
        spec = TOOL_DEFINITIONS.get(name)
        if spec is not None:
            tools.append(spec)
    return tools
