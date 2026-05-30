import secrets
from typing import Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.auth import extract_api_key, is_public_path
from app.core.config import Settings
from app.core.rbac import role_allows
from app.services.quota_store import QuotaStore


class AuthQuotaMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        settings: Settings,
        quota_store: Optional[QuotaStore],
    ) -> None:
        super().__init__(app)
        self.settings = settings
        self.quota_store = quota_store

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or is_public_path(path):
            return await call_next(request)

        if not self.settings.auth_enabled:
            return await call_next(request)

        api_keys = self.settings.api_keys
        if not api_keys:
            return await call_next(request)

        api_key = extract_api_key(request)
        if not api_key:
            return JSONResponse(status_code=401, content={"detail": "Missing API key"})

        key_config = None
        for candidate, config in api_keys.items():
            if secrets.compare_digest(api_key, candidate):
                key_config = config
                break
        if key_config is None:
            return JSONResponse(status_code=401, content={"detail": "Invalid API key"})

        if not role_allows(key_config.role, request.method, path):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Insufficient role for this endpoint",
                    "role": key_config.role,
                },
            )

        if self.quota_store is None:
            request.state.api_key = api_key
            request.state.api_role = key_config.role
            return await call_next(request)

        team_limit = self.settings.team_quotas.get(key_config.team)
        allowed, used, limit, team_used, team_limit_value = self.quota_store.consume_with_team(
            api_key,
            key_config.daily_quota,
            key_config.team,
            team_limit,
        )
        if not allowed:
            if team_used is not None and team_limit_value is not None:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Team daily quota exceeded",
                        "team": key_config.team,
                        "used": team_used,
                        "limit": team_limit_value,
                    },
                )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Daily quota exceeded",
                    "api_key": api_key,
                    "used": used,
                    "limit": limit,
                },
            )

        request.state.api_key = api_key
        request.state.api_role = key_config.role
        request.state.api_team = key_config.team
        request.state.quota_used = used
        request.state.quota_limit = limit
        request.state.team_quota_used = team_used
        request.state.team_quota_limit = team_limit_value
        return await call_next(request)
