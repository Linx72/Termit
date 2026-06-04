from __future__ import annotations

import json
from pathlib import Path

from app.domain.schemas import (
    AgentProfileCreateRequest,
    AgentProfileResponse,
    AgentTemplateResponse,
    TaskType,
)


class AgentTemplatesStore:
    def __init__(self, file_path: str = "./data/agent_templates.json") -> None:
        self.file_path = Path(file_path).resolve()

    def list_templates(self) -> list[AgentTemplateResponse]:
        if not self.file_path.exists():
            return []
        raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        templates: list[AgentTemplateResponse] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            templates.append(
                AgentTemplateResponse(
                    template_id=str(item.get("template_id", "")),
                    name=str(item.get("name", "")),
                    description=str(item.get("description", "")),
                    task_type=TaskType(str(item.get("task_type", "general"))),
                    system_prompt=str(item.get("system_prompt", "")),
                    enabled_tools=[str(tool) for tool in item.get("enabled_tools", [])],
                    use_tool_loop=bool(item.get("use_tool_loop", False)),
                    use_retrieval=bool(item.get("use_retrieval", False)),
                    allow_online=bool(item.get("allow_online", False)),
                    skill_ids=[str(skill) for skill in item.get("skill_ids", [])],
                )
            )
        return templates

    def get_template(self, template_id: str) -> AgentTemplateResponse | None:
        for item in self.list_templates():
            if item.template_id == template_id:
                return item
        return None

    def to_create_request(self, template_id: str) -> AgentProfileCreateRequest:
        template = self.get_template(template_id)
        if template is None:
            raise ValueError(f"Unknown agent template: {template_id}")
        return AgentProfileCreateRequest(
            name=template.name,
            description=template.description,
            system_prompt=template.system_prompt,
            task_type=template.task_type,
            enabled_tools=list(template.enabled_tools),
            use_tool_loop=template.use_tool_loop,
            use_retrieval=template.use_retrieval,
            allow_online=template.allow_online,
            skill_ids=list(template.skill_ids),
        )
