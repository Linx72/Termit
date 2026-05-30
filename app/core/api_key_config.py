from dataclasses import dataclass


@dataclass(frozen=True)
class ApiKeyConfig:
    daily_quota: int
    role: str
    team: str = "default"
