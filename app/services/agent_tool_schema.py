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
                    "provider": {"type": "string", "description": "openai or stub"},
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
}


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
