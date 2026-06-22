from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    AgentProfileResponse,
    AgentTemplateListResponse,
    ProjectRulesImportRequest,
    ProjectRulesResponse,
    ProjectRulesUpdateRequest,
    ProjectSkillsResponse,
    ProjectSkillsUpdateRequest,
    SkillSummaryResponse,
)
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.cursor_rules_importer import CursorRulesImporter
from app.services.project_rules_store import ProjectRulesStore
from app.services.skill_store import SkillStore
from app.state import (
    get_agent_registry_store,
    get_agent_templates_store,
    get_project_rules_store,
    get_skill_store,
)

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


@router.post("/agent-templates/{template_id}/ensure-agent", response_model=AgentProfileResponse)
async def ensure_agent_from_template(
    template_id: str,
    registry: AgentRegistryStore = Depends(get_agent_registry_store),
    templates: AgentTemplatesStore = Depends(get_agent_templates_store),
) -> AgentProfileResponse:
    try:
        request = templates.to_create_request(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for agent in registry.list_agents():
        if agent.name == request.name and agent.task_type == request.task_type:
            return agent
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


@router.get("/{project_id}/skills", response_model=ProjectSkillsResponse)
async def get_project_skills(
    project_id: str,
    rules_store: ProjectRulesStore = Depends(get_project_rules_store),
    skill_store: SkillStore = Depends(get_skill_store),
) -> ProjectSkillsResponse:
    payload = rules_store.get_rules(project_id)
    skills = payload.get("skills", [])
    pinned: list[str] = []
    if isinstance(skills, list):
        pinned = [str(item).strip() for item in skills if str(item).strip()]
    available = [
        SkillSummaryResponse(skill_id=item.skill_id, name=item.name, description=item.description)
        for item in skill_store.list_skills()
    ]
    return ProjectSkillsResponse(
        project_id=project_id,
        pinned_skill_ids=pinned,
        available_skills=available,
    )


@router.post("/{project_id}/skills", response_model=ProjectSkillsResponse)
async def update_project_skills(
    project_id: str,
    body: ProjectSkillsUpdateRequest,
    rules_store: ProjectRulesStore = Depends(get_project_rules_store),
    skill_store: SkillStore = Depends(get_skill_store),
) -> ProjectSkillsResponse:
    current = rules_store.get_rules(project_id)
    rules_store.save_rules(
        project_id,
        project_rules=str(current.get("project_rules", "")),
        user_rules=str(current.get("user_rules", "")),
        skills=[str(item).strip() for item in body.skill_ids if str(item).strip()],
    )
    return await get_project_skills(project_id, rules_store, skill_store)


@router.post("/{project_id}/rules/import-cursor", response_model=ProjectRulesResponse)
async def import_cursor_project_rules(
    project_id: str,
    body: ProjectRulesImportRequest,
    store: ProjectRulesStore = Depends(get_project_rules_store),
) -> ProjectRulesResponse:
    current = store.get_rules(project_id)
    importer = CursorRulesImporter()
    merged_rules = importer.merge_into_project_rules(
        str(current.get("project_rules", "")),
        body.workspace_root,
        active_path=body.active_path,
    )
    payload = store.save_rules(
        project_id,
        project_rules=merged_rules,
        user_rules=str(current.get("user_rules", "")),
        skills=[str(item) for item in current.get("skills", []) if str(item).strip()],
    )
    return ProjectRulesResponse.model_validate(payload)
