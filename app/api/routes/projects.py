from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    AgentProfileResponse,
    AgentTemplateListResponse,
    ProjectRulesResponse,
    ProjectRulesUpdateRequest,
)
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.project_rules_store import ProjectRulesStore
from app.state import get_agent_registry_store, get_agent_templates_store, get_project_rules_store

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/agent-templates", response_model=AgentTemplateListResponse)
async def list_agent_templates(
    store: AgentTemplatesStore = Depends(get_agent_templates_store),
) -> AgentTemplateListResponse:
    return AgentTemplateListResponse(templates=store.list_templates())


@router.post("/agent-templates/{template_id}/create-agent", response_model=AgentProfileResponse)
async def create_agent_from_template(
    template_id: str,
    registry: AgentRegistryStore = Depends(get_agent_registry_store),
    templates: AgentTemplatesStore = Depends(get_agent_templates_store),
) -> AgentProfileResponse:
    try:
        request = templates.to_create_request(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return registry.create_agent(request)


@router.get("/{project_id}/rules", response_model=ProjectRulesResponse)
async def get_project_rules(
    project_id: str,
    store: ProjectRulesStore = Depends(get_project_rules_store),
) -> ProjectRulesResponse:
    payload = store.get_rules(project_id)
    return ProjectRulesResponse.model_validate(payload)


@router.post("/{project_id}/rules", response_model=ProjectRulesResponse)
async def update_project_rules(
    project_id: str,
    body: ProjectRulesUpdateRequest,
    store: ProjectRulesStore = Depends(get_project_rules_store),
) -> ProjectRulesResponse:
    payload = store.save_rules(
        project_id,
        project_rules=body.project_rules,
        user_rules=body.user_rules,
        skills=body.skills,
    )
    return ProjectRulesResponse.model_validate(payload)
