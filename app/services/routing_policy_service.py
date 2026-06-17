from __future__ import annotations

import json
import random
from datetime import datetime, timezone
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
    shadow_model: str = ""
    shadow_traffic_percent: float = 0.0


class RoutingPolicyService:
    def __init__(
        self,
        repo_profiles_path: str = "./data/repo_model_profiles.json",
        benchmarks_path: str = "./data/routing_benchmarks.json",
        adapter_resolver: Optional["FinetuneAdapterResolver"] = None,
    ) -> None:
        self._repo_profiles_path = Path(repo_profiles_path)
        self._benchmarks_path = Path(benchmarks_path)
        self._adapter_resolver = adapter_resolver
        self._profiles_mtime: float = -1.0
        self._profiles: list[RepoModelProfile] = []
        self._benchmark_scores: dict[str, dict[str, float]] = {}
        self._reload_profiles_if_changed()
        self._benchmark_scores = self._load_benchmarks(benchmarks_path)

    def _reload_profiles_if_changed(self) -> None:
        path = self._repo_profiles_path
        mtime = path.stat().st_mtime if path.exists() else 0.0
        if mtime == self._profiles_mtime:
            return
        self._profiles = self._load_profiles(str(path))
        self._profiles_mtime = mtime

    def list_repo_profiles(self) -> list[RepoModelProfile]:
        self._reload_profiles_if_changed()
        return list(self._profiles)

    def get_repo_profile(self, profile_id: str) -> Optional[RepoModelProfile]:
        self._reload_profiles_if_changed()
        return next((item for item in self._profiles if item.profile_id == profile_id), None)

    def resolve_repo_model(
        self,
        *,
        profile_id: Optional[str],
        path_prefix: str,
        task_type: TaskType,
    ) -> Optional[str]:
        self._reload_profiles_if_changed()
        if profile_id:
            profile = self.get_repo_profile(profile_id)
            if profile is not None:
                return self._pick_profile_model(profile)
            if self._adapter_resolver is not None:
                adapter_model = self._adapter_resolver.resolve_model(profile_id)
                if adapter_model:
                    return adapter_model

        normalized_prefix = path_prefix.strip().replace("\\", "/")
        for profile in self._profiles:
            if profile.path_prefix and normalized_prefix.startswith(profile.path_prefix):
                if profile.task_type == task_type.value or profile.task_type == "general":
                    return self._pick_profile_model(profile)
        return None

    def _pick_profile_model(self, profile: RepoModelProfile) -> str:
        shadow = profile.shadow_model.strip()
        if shadow and profile.shadow_traffic_percent > 0:
            if random.random() < min(1.0, profile.shadow_traffic_percent / 100.0):
                return shadow
        return profile.preferred_model

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

    def update_benchmark_scores(
        self,
        updates: dict[str, dict[str, float]],
        *,
        blend_alpha: float = 0.0,
        persist: bool = True,
    ) -> dict[str, object]:
        """Merge or replace benchmark scores and optionally persist to disk."""
        alpha = max(0.0, min(1.0, float(blend_alpha)))
        updated_models: list[str] = []
        for model, task_scores in updates.items():
            model_key = str(model).strip()
            if not model_key:
                continue
            bucket = self._benchmark_scores.setdefault(model_key, {})
            model_changed = False
            for task, raw_score in task_scores.items():
                task_key = str(task).strip()
                if not task_key:
                    continue
                score = round(float(raw_score), 4)
                old = bucket.get(task_key)
                if old is None:
                    merged = score
                else:
                    merged = round(alpha * score + (1.0 - alpha) * float(old), 4)
                if old != merged:
                    model_changed = True
                bucket[task_key] = merged
            if model_changed:
                updated_models.append(model_key)
        if persist and updated_models:
            self._persist_benchmarks()
        return {
            "updated_models": sorted(updated_models),
            "blend_alpha": alpha,
            "benchmark_models": self.list_benchmark_models(),
        }

    def reload_benchmarks(self) -> None:
        self._benchmark_scores = self._load_benchmarks(str(self._benchmarks_path))

    def _persist_benchmarks(self) -> None:
        path = self._benchmarks_path
        existing: dict[str, object] = {}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        version = int(existing.get("version", 1) or 1) + 1
        payload = {
            "version": version,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "scores": self._benchmark_scores,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

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
                    shadow_model=str(item.get("shadow_model", "")),
                    shadow_traffic_percent=float(item.get("shadow_traffic_percent", 0.0) or 0.0),
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
