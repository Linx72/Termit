from __future__ import annotations

from typing import Optional

from app.core.config import Settings
from app.domain.schemas import TeamListResponse, TeamUsageEntry, TeamUsageResponse
from app.services.quota_store import QuotaStore


class TeamWorkspaceService:
    def __init__(self, settings: Settings, quota_store: QuotaStore) -> None:
        self.settings = settings
        self.quota_store = quota_store

    def list_teams(self) -> TeamListResponse:
        teams = set(self.settings.team_quotas.keys())
        for key_config in self.settings.api_keys.values():
            teams.add(key_config.team)
        return TeamListResponse(teams=sorted(teams))

    def team_usage(
        self,
        *,
        team_filter: Optional[str] = None,
        caller_team: Optional[str] = None,
        admin_view: bool = False,
    ) -> TeamUsageResponse:
        if not self.settings.auth_enabled:
            return TeamUsageResponse(auth_enabled=False, entries=[])

        usage_map = self.quota_store.list_team_usage_for_day()
        teams = set(self.settings.team_quotas.keys())
        for key_config in self.settings.api_keys.values():
            teams.add(key_config.team)

        if team_filter:
            teams = {team_filter} if team_filter in teams else set()
        elif not admin_view and caller_team:
            teams = {caller_team}

        entries: list[TeamUsageEntry] = []
        for team in sorted(teams):
            used = usage_map.get(team, 0)
            limit = self.settings.team_quotas.get(team)
            remaining = max(limit - used, 0) if limit is not None else None
            percent = round((used / limit) * 100, 2) if limit else None
            member_keys = sum(
                1 for cfg in self.settings.api_keys.values() if cfg.team == team
            )
            entries.append(
                TeamUsageEntry(
                    team=team,
                    used=used,
                    limit=limit,
                    remaining=remaining,
                    usage_percent=percent,
                    member_keys=member_keys,
                )
            )
        return TeamUsageResponse(auth_enabled=True, entries=entries)
