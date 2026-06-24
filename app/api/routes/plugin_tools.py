"""
API-роуты для моста Plugin ↔ Chat Tools.
Регистрирует инструменты плагинов в deferred_tool_catalog.
"""

from fastapi import APIRouter, HTTPException

from app.services.agent_tool_schema import deferred_tool_catalog

router = APIRouter(prefix="/api/plugins", tags=["plugin-tools"])

# Реестр инструментов от плагинов
_plugin_tools: dict[str, dict[str, object]] = {}


@router.get("/tools")
async def list_plugin_tools():
    """Получить все инструменты от enabled плагинов."""
    tools = []
    for name, schema in _plugin_tools.items():
        func = schema.get("function", {})
        tools.append({
            "name": name,
            "description": func.get("description", ""),
            "plugin_name": schema.get("plugin_name", "unknown"),
            "parameters": func.get("parameters", {}).get("properties", {}),
        })
    return tools


@router.post("/tools/sync")
async def sync_plugin_tools(payload: dict):
    """
    Зарегистрировать имена инструментов от плагинов в agent_tool_schema.
    
    POST body: {"tool_names": ["plugin_search", "plugin_deploy", ...]}
    """
    tool_names = payload.get("tool_names", [])
    if not isinstance(tool_names, list):
        raise HTTPException(status_code=400, detail="tool_names must be a list")

    # Регистрируем в deferred_tool_catalog если инструмент есть в _plugin_tools
    registered = 0
    for name in tool_names:
        if name in _plugin_tools:
            if name not in deferred_tool_catalog:
                deferred_tool_catalog[name] = _plugin_tools[name]
                registered += 1

    return {
        "status": "ok",
        "registered": registered,
        "total_plugin_tools": len(_plugin_tools),
        "total_catalog_tools": len(deferred_tool_catalog),
    }


@router.post("/tools/register")
async def register_plugin_tool(payload: dict):
    """
    Зарегистрировать один инструмент от плагина.
    
    POST body: {
        "tool_name": "plugin_search",
        "description": "Search in codebase",
        "parameters": {"query": {"type": "string", "description": "..."}},
        "plugin_name": "my-plugin"
    }
    """
    tool_name = payload.get("tool_name", "")
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    params = payload.get("parameters", {})
    properties = {}
    for pname, pinfo in params.items():
        properties[pname] = {
            "type": pinfo.get("type", "string"),
            "description": pinfo.get("description", ""),
        }

    schema = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": payload.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": [pname for pname, pinfo in params.items() if pinfo.get("required")],
            },
        },
        "plugin_name": payload.get("plugin_name", "unknown"),
    }

    _plugin_tools[tool_name] = schema

    # Авто-регистрация в deferred_tool_catalog
    if tool_name not in deferred_tool_catalog:
        deferred_tool_catalog[tool_name] = schema

    return {"status": "ok", "tool_name": tool_name}


@router.delete("/tools/{tool_name}")
async def unregister_plugin_tool(tool_name: str):
    """Удалить инструмент плагина из реестра."""
    _plugin_tools.pop(tool_name, None)
    deferred_tool_catalog.pop(tool_name, None)
    return {"status": "ok", "tool_name": tool_name}
