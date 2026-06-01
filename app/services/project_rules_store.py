from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class ProjectRulesStore:
    def __init__(self, base_dir: str = "./data/projects") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _project_path(self, project_id: str) -> Path:
        safe = project_id.strip().replace("/", "_").replace("..", "_")
        if not safe:
            raise ValueError("project_id is required.")
        return self.base_dir / safe / "rules.json"

    def get_rules(self, project_id: str) -> dict[str, object]:
        path = self._project_path(project_id)
        if not path.exists():
            return {
                "project_id": project_id,
                "project_rules": "",
                "user_rules": "",
                "skills": [],
            }
        with self._lock:
            payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Invalid rules payload.")
        payload.setdefault("project_id", project_id)
        payload.setdefault("project_rules", "")
        payload.setdefault("user_rules", "")
        payload.setdefault("skills", [])
        return payload

    def save_rules(
        self,
        project_id: str,
        *,
        project_rules: str,
        user_rules: str,
        skills: list[str],
    ) -> dict[str, object]:
        path = self._project_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "project_id": project_id,
            "project_rules": project_rules.strip(),
            "user_rules": user_rules.strip(),
            "skills": [item.strip() for item in skills if item.strip()],
        }
        with self._lock:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def format_for_prompt(self, project_id: str) -> str:
        payload = self.get_rules(project_id)
        sections: list[str] = []
        project_rules = str(payload.get("project_rules", "")).strip()
        user_rules = str(payload.get("user_rules", "")).strip()
        skills = payload.get("skills", [])
        if project_rules:
            sections.append("[Project rules]\n" + project_rules)
        if user_rules:
            sections.append("[User rules]\n" + user_rules)
        if isinstance(skills, list) and skills:
            skill_lines = "\n".join(f"- {str(item)}" for item in skills if str(item).strip())
            if skill_lines:
                sections.append("[Agent skills]\n" + skill_lines)
        return "\n\n".join(sections).strip()
