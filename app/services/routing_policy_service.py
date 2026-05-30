from __future__ import annotations

import json
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

from app.domain.schemas import TaskType


@dataclass(frozen=True)
class RepoModelProfile:
    profile_id: str
    title: str
    path_prefix: str
    task_type: str
    preferred_model: str
    description: str = ""


class RoutingPolicyService:
    def __init__(
        self,
        repo_profiles_path: str = "./data/repo_model_profiles.json",
        benchmarks_path: str = "./data/routing_benchmarks.json",
    ) -> None:
        self._profiles = self._load_profiles(repo_profiles_path)
        self._benchmark_scores = self._load_benchmarks(benchmarks_path)

    def list_repo_profiles(self) -> list[RepoModelProfile]:
        return list(self._profiles)

    def get_repo_profile(self, profile_id: str) -> Optional[RepoModelProfile]:
        return next((item for item in self._profiles if item.profile_id == profile_id), None)

    def resolve_repo_model(
        self,
        *,
        profile_id: Optional[str],
        path_prefix: str,
        task_type: TaskType,
    ) -> Optional[str]:
        if profile_id:
            profile = self.get_repo_profile(profile_id)
            if profile is not None:
                return profile.preferred_model

        normalized_prefix = path_prefix.strip().replace("\\", "/")
        for profile in self._profiles:
            if profile.path_prefix and normalized_prefix.startswith(profile.path_prefix):
                if profile.task_type == task_type.value or profile.task_type == "general":
                    return profile.preferred_model
        return None

    def rank_models_for_task(
        self,
        models: list[str],
        task_type: TaskType,
    ) -> list[str]:
        if not models:
            return []
        scored: list[tuple[str, float]] = []
        task_key = task_type.value
        for model in models:
            model_scores = self._benchmark_scores.get(model, {})
            score = float(model_scores.get(task_key, model_scores.get("general", 0.5)))
            scored.append((model, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [model for model, _ in scored]

    def list_benchmark_models(self) -> list[str]:
        return sorted(self._benchmark_scores.keys())

    def benchmark_score(self, model: str, task_type: TaskType) -> Optional[float]:
        model_scores = self._benchmark_scores.get(model)
        if not model_scores:
            return None
        return float(model_scores.get(task_type.value, model_scores.get("general")))

    def _load_profiles(self, profiles_path: str) -> list[RepoModelProfile]:
        path = Path(profiles_path)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        profiles: list[RepoModelProfile] = []
        for item in raw:
            profiles.append(
                RepoModelProfile(
                    profile_id=str(item["profile_id"]),
                    title=str(item.get("title", item["profile_id"])),
                    path_prefix=str(item.get("path_prefix", "")),
                    task_type=str(item.get("task_type", "general")),
                    preferred_model=str(item["preferred_model"]),
                    description=str(item.get("description", "")),
                )
            )
        return profiles

    def _load_benchmarks(self, benchmarks_path: str) -> dict[str, dict[str, float]]:
        path = Path(benchmarks_path)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        scores = raw.get("scores", {})
        parsed: dict[str, dict[str, float]] = {}
        for model, task_scores in scores.items():
            if not isinstance(task_scores, dict):
                continue
            parsed[str(model)] = {str(k): float(v) for k, v in task_scores.items()}
        return parsed
