from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import get_settings
from app.domain.schemas import (
    AgentRunRequest,
    AutomationAgentRunWebhookRequest,
    AutomationAgentRunWebhookResponse,
    WebAutomationRequest,
    WebAutomationResponse,
)
from app.services.agent_service import AgentNotFoundError, AgentQueueFullError, AgentService, GuardrailBlockedError
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.browser_workflow_service import BrowserWorkflowService, WebWorkflowError
from app.state import get_agent_registry_store, get_agent_service, get_agent_templates_store, get_browser_workflow_service

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _resolve_agent_id(
    payload: AutomationAgentRunWebhookRequest,
    *,
    registry,
    templates: AgentTemplatesStore,
) -> str:
    if payload.agent_id:
        profile = registry.get_agent(payload.agent_id.strip())
        if profile is None:
            raise HTTPException(status_code=404, detail=f"Agent not found: {payload.agent_id}")
        return profile.agent_id
    template_id = (payload.template_id or "web-app-vite").strip()
    try:
        request = templates.to_create_request(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for agent in registry.list_agents():
        if agent.name == request.name and agent.task_type == request.task_type:
            return agent.agent_id
    return registry.create_agent(request).agent_id


@router.post("/web", response_model=WebAutomationResponse)
async def run_web_automation(
    payload: WebAutomationRequest,
    service: BrowserWorkflowService = Depends(get_browser_workflow_service),
) -> WebAutomationResponse:
    try:
        return service.run(payload)
    except WebWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhook/agent-run", response_model=AutomationAgentRunWebhookResponse)
async def webhook_agent_run(
    payload: AutomationAgentRunWebhookRequest,
    x_termit_webhook_secret: str | None = Header(default=None, alias="X-Termit-Webhook-Secret"),
    service: AgentService = Depends(get_agent_service),
    registry=Depends(get_agent_registry_store),
    templates: AgentTemplatesStore = Depends(get_agent_templates_store),
) -> AutomationAgentRunWebhookResponse:
    settings = get_settings()
    expected = settings.automation_webhook_secret.strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Automation webhook is not configured.")
    if (x_termit_webhook_secret or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    agent_id = _resolve_agent_id(payload, registry=registry, templates=templates)
    run_payload = AgentRunRequest(
        input=payload.input,
        project_id=payload.project_id,
        run_mode=payload.run_mode,
        priority=payload.priority,
        use_tool_loop=True,
    )
    try:
        created = service.create_run(agent_id, run_payload)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentQueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except GuardrailBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AutomationAgentRunWebhookResponse(
        run_id=created.run_id,
        state=created.state.value,
        agent_id=agent_id,
        queued_position=created.queued_position,
    )
