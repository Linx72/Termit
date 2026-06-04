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
