from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path

from app.domain.schemas import (
    AgentScheduleCreateRequest,
    AgentScheduleListResponse,
    AgentScheduleResponse,
    GuardrailCheckRequest,
    GuardrailCheckResponse,
    HookStatusResponse,
    McpCursorImportRequest,
    McpCursorImportResponse,
    McpInvokeRequest,
    McpInvokeResponse,
    McpCapabilitiesResponse,
    McpResourceReadRequest,
    McpResourceReadResponse,
    McpPromptGetRequest,
    McpPromptGetResponse,
    McpPingResponse,
    McpPromptArgumentResponse,
    McpPromptListResponse,
    McpPromptResponse,
    McpResourceListResponse,
    McpResourceResponse,
    McpToolListResponse,
    McpToolResponse,
    McpServerCreateRequest,
    McpServerListResponse,
    McpServerResponse,
    PlatformSearchHitResponse,
    PlatformSearchRequest,
    PlatformSearchResponse,
    SkillDetailResponse,
    SkillListResponse,
    SkillSelectRequest,
    SkillSelectResponse,
    SkillSelectionItemResponse,
    SkillSummaryResponse,
    TraceSpanListResponse,
    TraceSpanResponse,
)
from app.core.config import get_settings
from app.services.agent_service import AgentNotFoundError, AgentService
from app.services.search_provider import (
    PerplexitySearchProvider,
    SearxngSearchProvider,
    StubSearchProvider,
)
from app.services.agent_hook_service import AgentHookService
from app.services.agent_schedule_service import AgentScheduleService
from app.services.guardrail_service import GuardrailService
from app.services.mcp_registry_service import McpRegistryService
from app.services.skill_store import SkillStore
from app.services.skill_selector_service import SkillSelectorService
from app.services.trace_span_store import TraceSpanStore
from app.state import (
    get_agent_hook_service,
    get_agent_schedule_service,
    get_agent_service,
    get_guardrail_service,
    get_mcp_registry_service,
    get_search_provider,
    get_skill_store,
    get_skill_selector_service,
    get_trace_span_store,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(store: SkillStore = Depends(get_skill_store)) -> SkillListResponse:
    skills = [
        SkillSummaryResponse(skill_id=item.skill_id, name=item.name, description=item.description)
        for item in store.list_skills()
    ]
    return SkillListResponse(skills=skills)


@router.get("/skills/{skill_id}", response_model=SkillDetailResponse)
async def get_skill(
    skill_id: str,
    store: SkillStore = Depends(get_skill_store),
) -> SkillDetailResponse:
    skill = store.get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    return SkillDetailResponse(
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.description,
        content=skill.content,
    )


@router.post("/skills/select", response_model=SkillSelectResponse)
async def select_skills(
    payload: SkillSelectRequest,
    selector: SkillSelectorService = Depends(get_skill_selector_service),
) -> SkillSelectResponse:
    result = selector.select_skills(
        instruction=payload.instruction,
        task_type=payload.task_type,
        pinned_skill_ids=list(payload.pinned_skill_ids),
        changed_files=list(payload.changed_files),
        max_skills=payload.max_skills,
        auto_select_enabled=payload.auto_select_enabled,
    )
    return SkillSelectResponse(
        selected_skill_ids=list(result.selected_skill_ids),
        selections=[
            SkillSelectionItemResponse(
                skill_id=item.skill_id,
                name=item.name,
                score=item.score,
                matched_terms=list(item.matched_terms),
                source=item.source,
            )
            for item in result.selections
        ],
        auto_select_enabled=result.auto_select_enabled,
    )


@router.get("/hooks/status", response_model=HookStatusResponse)
async def hooks_status(hooks: AgentHookService = Depends(get_agent_hook_service)) -> HookStatusResponse:
    return HookStatusResponse(
        enabled=hooks.enabled,
        webhook_configured=bool(hooks.webhook_url),
        configured_events=hooks.list_configured_events(),
        local_script_hooks=hooks.count_local_scripts(),
    )


@router.post("/guardrails/check", response_model=GuardrailCheckResponse)
async def guardrails_check(
    payload: GuardrailCheckRequest,
    guardrails: GuardrailService = Depends(get_guardrail_service),
) -> GuardrailCheckResponse:
    if payload.kind == "patch":
        result = guardrails.check_patch_content(payload.text)
    else:
        result = guardrails.check_prompt(payload.text)
    return GuardrailCheckResponse(
        allowed=result.allowed,
        reason=result.reason,
        severity=result.severity,
    )


@router.get("/runs/{run_id}/spans", response_model=TraceSpanListResponse)
async def list_run_spans(
    run_id: str,
    limit: int = 100,
    spans: TraceSpanStore = Depends(get_trace_span_store),
) -> TraceSpanListResponse:
    items = spans.list_for_run(run_id, limit=limit)
    return TraceSpanListResponse(
        run_id=run_id,
        spans=[TraceSpanResponse(**item) for item in items],
    )


@router.get("/runs/{run_id}/spans/otel")
async def export_run_spans_otel(
    run_id: str,
    limit: int = 100,
    spans: TraceSpanStore = Depends(get_trace_span_store),
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "resourceSpans": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "termit"}}]},
                "scopeSpans": [
                    {
                        "scope": {"name": "termit.trace"},
                        "spans": spans.export_otel_json(run_id, limit=limit),
                    }
                ],
            }
        ],
    }


@router.get("/mcp/servers", response_model=McpServerListResponse)
async def list_mcp_servers(
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpServerListResponse:
    servers = [
        McpServerResponse(
            server_id=item.server_id,
            name=item.name,
            command=item.command,
            args=item.args,
            enabled=item.enabled,
            allowed_tools=item.allowed_tools or [],
        )
        for item in registry.list_servers()
    ]
    return McpServerListResponse(servers=servers)


@router.post("/mcp/import-cursor", response_model=McpCursorImportResponse)
async def import_cursor_mcp(
    payload: McpCursorImportRequest,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpCursorImportResponse:
    source_path = (
        Path(payload.path).expanduser()
        if payload.path
        else Path(payload.workspace_root).expanduser().resolve() / ".cursor" / "mcp.json"
    )
    try:
        imported = registry.import_from_mcp_file(source_path.resolve(), merge=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    servers = [
        McpServerResponse(
            server_id=item.server_id,
            name=item.name,
            command=item.command,
            args=item.args,
            enabled=item.enabled,
            allowed_tools=item.allowed_tools or [],
        )
        for item in registry.list_servers()
    ]
    return McpCursorImportResponse(imported=len(imported), servers=servers)


@router.post("/mcp/servers", response_model=McpServerResponse)
async def upsert_mcp_server(
    payload: McpServerCreateRequest,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpServerResponse:
    record = registry.upsert_server(
        name=payload.name,
        command=payload.command,
        args=payload.args,
        enabled=payload.enabled,
        allowed_tools=payload.allowed_tools or None,
        server_id=payload.server_id,
    )
    return McpServerResponse(
        server_id=record.server_id,
        name=record.name,
        command=record.command,
        args=record.args,
        enabled=record.enabled,
        allowed_tools=record.allowed_tools or [],
    )


@router.post("/mcp/servers/{server_id}/invoke", response_model=McpInvokeResponse)
async def invoke_mcp_tool(
    server_id: str,
    payload: McpInvokeRequest,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpInvokeResponse:
    try:
        result = registry.invoke_tool(server_id, payload.tool_name, payload.arguments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return McpInvokeResponse(result_json=result)


@router.get("/mcp/servers/{server_id}/tools", response_model=McpToolListResponse)
async def list_mcp_server_tools(
    server_id: str,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpToolListResponse:
    try:
        tools = registry.list_tools(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return McpToolListResponse(
        server_id=server_id,
        tools=[
            McpToolResponse(
                name=item.name,
                description=item.description,
                input_schema=item.input_schema,
            )
            for item in tools
        ],
    )


@router.get("/mcp/servers/{server_id}/ping", response_model=McpPingResponse)
async def ping_mcp_server(
    server_id: str,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpPingResponse:
    try:
        ok = registry.ping_server(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return McpPingResponse(server_id=server_id, ok=ok)


@router.get("/mcp/servers/{server_id}/resources", response_model=McpResourceListResponse)
async def list_mcp_server_resources(
    server_id: str,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpResourceListResponse:
    try:
        resources = registry.list_resources(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return McpResourceListResponse(
        server_id=server_id,
        resources=[
            McpResourceResponse(
                uri=item.uri,
                name=item.name,
                description=item.description,
                mime_type=item.mime_type,
            )
            for item in resources
        ],
    )


@router.get("/mcp/servers/{server_id}/prompts", response_model=McpPromptListResponse)
async def list_mcp_server_prompts(
    server_id: str,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpPromptListResponse:
    try:
        prompts = registry.list_prompts(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return McpPromptListResponse(
        server_id=server_id,
        prompts=[
            McpPromptResponse(
                name=item.name,
                description=item.description,
                arguments=[
                    McpPromptArgumentResponse(
                        name=str(arg.get("name", "")),
                        description=str(arg.get("description", "")),
                        required=bool(arg.get("required", False)),
                    )
                    for arg in item.arguments
                    if isinstance(arg, dict)
                ],
            )
            for item in prompts
        ],
    )


@router.get("/mcp/servers/{server_id}/capabilities", response_model=McpCapabilitiesResponse)
async def mcp_server_capabilities(
    server_id: str,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpCapabilitiesResponse:
    try:
        payload = registry.get_capabilities(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return McpCapabilitiesResponse.model_validate(payload)


@router.post("/mcp/servers/{server_id}/resources/read", response_model=McpResourceReadResponse)
async def read_mcp_resource(
    server_id: str,
    payload: McpResourceReadRequest,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpResourceReadResponse:
    try:
        result = registry.read_resource(server_id, payload.uri)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    contents_raw = result.get("contents", [])
    contents = [item for item in contents_raw if isinstance(item, dict)] if isinstance(contents_raw, list) else []
    return McpResourceReadResponse(server_id=server_id, uri=payload.uri, contents=contents)


@router.post("/mcp/servers/{server_id}/prompts/get", response_model=McpPromptGetResponse)
async def get_mcp_prompt(
    server_id: str,
    payload: McpPromptGetRequest,
    registry: McpRegistryService = Depends(get_mcp_registry_service),
) -> McpPromptGetResponse:
    try:
        result = registry.get_prompt(server_id, payload.name, payload.arguments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    messages_raw = result.get("messages", [])
    messages = [item for item in messages_raw if isinstance(item, dict)] if isinstance(messages_raw, list) else []
    return McpPromptGetResponse(
        server_id=server_id,
        name=payload.name,
        description=str(result.get("description", "")),
        messages=messages,
    )


@router.post("/schedules", response_model=AgentScheduleResponse)
async def create_schedule(
    payload: AgentScheduleCreateRequest,
    agent_service: AgentService = Depends(get_agent_service),
    schedules: AgentScheduleService = Depends(get_agent_schedule_service),
) -> AgentScheduleResponse:
    try:
        agent_service.get_agent(payload.agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from app.domain.schemas import AgentRunRequest

    run_payload = AgentRunRequest(
        input=payload.input,
        use_tool_loop=payload.use_tool_loop,
    )
    created = schedules.create_schedule(
        agent_id=payload.agent_id,
        cron=payload.cron,
        payload=run_payload,
    )
    return AgentScheduleResponse(**created)


@router.get("/schedules", response_model=AgentScheduleListResponse)
async def list_schedules(
    agent_id: Optional[str] = None,
    schedules: AgentScheduleService = Depends(get_agent_schedule_service),
) -> AgentScheduleListResponse:
    items = [
        AgentScheduleResponse(
            schedule_id=str(row["schedule_id"]),
            agent_id=str(row["agent_id"]),
            cron=str(row["cron"]),
            enabled=bool(row.get("enabled", 1)),
            next_run_at=row.get("next_run_at"),
            last_run_at=row.get("last_run_at"),
        )
        for row in schedules.list_schedules(agent_id=agent_id)
    ]
    return AgentScheduleListResponse(schedules=items)


@router.get("/search/status")
async def search_status() -> dict[str, object]:
    settings = get_settings()
    provider = get_search_provider()
    if isinstance(provider, PerplexitySearchProvider):
        label = "perplexity"
    elif isinstance(provider, SearxngSearchProvider):
        label = "searxng"
    elif isinstance(provider, StubSearchProvider):
        label = "stub"
    else:
        label = getattr(provider, "provider_label", "http")
    configured = label != "stub"
    return {
        "configured": configured,
        "provider": label,
        "search_api_url": bool(settings.search_api_url.strip()),
        "search_provider_setting": settings.search_provider,
    }


@router.post("/search", response_model=PlatformSearchResponse)
async def search_web(
    payload: PlatformSearchRequest,
    provider=Depends(get_search_provider),
) -> PlatformSearchResponse:
    result = provider.search(payload.query, max_results=payload.max_results)
    return PlatformSearchResponse(
        query=result.query,
        provider=result.provider,
        hits=[
            PlatformSearchHitResponse(title=hit.title, url=hit.url, snippet=hit.snippet)
            for hit in result.hits
        ],
    )
