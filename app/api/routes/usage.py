from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import extract_api_key
from app.core.config import Settings, get_settings
from app.domain.schemas import UsageStatusResponse
from app.services.quota_store import QuotaStore
from app.state import get_quota_store

router = APIRouter(prefix="/api", tags=["usage"])


@router.get("/usage", response_model=UsageStatusResponse)
async def usage_status(
    request: Request,
    settings: Settings = Depends(get_settings),
    quota_store: QuotaStore = Depends(get_quota_store),
) -> UsageStatusResponse:
    if not settings.auth_enabled or not settings.api_keys:
        return UsageStatusResponse(
            auth_enabled=False,
            api_key=None,
            role=None,
            used=0,
            limit=0,
            remaining=0,
        )

    api_key = extract_api_key(request)
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_config = settings.api_keys.get(api_key)
    if key_config is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    used = quota_store.get_usage(api_key)
    remaining = max(key_config.daily_quota - used, 0)
    usage_percent = round((used / key_config.daily_quota) * 100, 2) if key_config.daily_quota else 0.0
    team_limit = settings.team_quotas.get(key_config.team)
    team_used = quota_store.get_team_usage(key_config.team) if team_limit is not None else None
    team_remaining = None
    team_percent = None
    if team_limit is not None and team_used is not None:
        team_remaining = max(team_limit - team_used, 0)
        team_percent = round((team_used / team_limit) * 100, 2) if team_limit else 0.0
    return UsageStatusResponse(
        auth_enabled=True,
        api_key=api_key,
        role=key_config.role,
        team=key_config.team,
        used=used,
        limit=key_config.daily_quota,
        remaining=remaining,
        usage_percent=usage_percent,
        team_used=team_used,
        team_limit=team_limit,
        team_remaining=team_remaining,
        team_usage_percent=team_percent,
    )
