from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class FinetuneAdapterResolver:
    """Resolve latest finetuned Ollama model id for a repo profile."""

    def __init__(
        self,
        adapters_path: str = "./data/finetune/adapters.json",
        adapters_dir: str = "./data/finetune/adapters",
    ) -> None:
        self.adapters_path = Path(adapters_path)
        self.adapters_dir = Path(adapters_dir)

    def resolve_model(
        self,
        repo_profile_id: Optional[str],
        *,
        task_type: str = "coding",
    ) -> Optional[str]:
        del task_type  # reserved for per-task adapter routing
        if not repo_profile_id:
            return None
        profile_id = repo_profile_id.strip()
        model = self._resolve_from_registry(profile_id)
        if model:
            return model
        return self._resolve_from_filesystem(profile_id)

    def _resolve_from_registry(self, profile_id: str) -> Optional[str]:
        if not self.adapters_path.exists():
            return None
        try:
            raw = json.loads(self.adapters_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        adapters = raw.get("adapters", [])
        if not isinstance(adapters, list):
            return None

        matches = [
            item
            for item in adapters
            if isinstance(item, dict)
            and str(item.get("repo_profile_id", "")) == profile_id
        ]
        if not matches:
            return None

        def _sort_key(item: dict) -> str:
            return str(item.get("registered_at", ""))

        latest = sorted(matches, key=_sort_key, reverse=True)[0]
        model = str(latest.get("model", "")).strip()
        return model or None

    def _resolve_from_filesystem(self, profile_id: str) -> Optional[str]:
        repo_dir = self.adapters_dir / profile_id
        if not repo_dir.is_dir():
            return None
        for name in ("adapter.gguf", "latest.gguf", "model.gguf"):
            if (repo_dir / name).is_file():
                return f"ollama:{profile_id}-ft"
        manifests = sorted(repo_dir.glob("*.gguf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if manifests:
            return f"ollama:{profile_id}-ft"
        return None

    def list_for_profile(self, repo_profile_id: str) -> list[dict[str, object]]:
        if not self.adapters_path.exists():
            return []
        try:
            raw = json.loads(self.adapters_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        adapters = raw.get("adapters", [])
        if not isinstance(adapters, list):
            return []
        return [
            item
            for item in adapters
            if isinstance(item, dict)
            and str(item.get("repo_profile_id", "")) == repo_profile_id.strip()
        ]
