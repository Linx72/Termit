from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.domain.schemas import TeamListResponse, TeamUsageResponse
from app.services.team_workspace_service import TeamWorkspaceService
from app.state import get_quota_store, get_team_workspace_service

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=TeamListResponse)
async def list_teams(
    service: TeamWorkspaceService = Depends(get_team_workspace_service),
) -> TeamListResponse:
    return service.list_teams()


@router.get("/usage", response_model=TeamUsageResponse)
async def team_usage(
    request: Request,
    team: Optional[str] = None,
    settings: Settings = Depends(get_settings),
    service: TeamWorkspaceService = Depends(get_team_workspace_service),
) -> TeamUsageResponse:
    if not settings.auth_enabled:
        return service.team_usage(admin_view=True)

    caller_role = getattr(request.state, "api_role", None)
    caller_team = getattr(request.state, "api_team", None)
    if caller_role == "admin":
        return service.team_usage(team_filter=team, admin_view=True)
    if team and team != caller_team:
        raise HTTPException(status_code=403, detail="Cannot view another team's usage.")
    return service.team_usage(team_filter=caller_team, caller_team=caller_team, admin_view=False)
