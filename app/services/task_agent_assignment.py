from __future__ import annotations

from app.domain.schemas import TaskType


def resolve_primary_template_id(task_type: TaskType, input_text: str) -> str:
    text = input_text.lower()
    if task_type == TaskType.online_project:
        return "online-project-manager"
    if task_type == TaskType.online_research:
        if any(term in text for term in ("deep", "comprehensive", "thorough")):
            return "research-deep"
        return "research-fast"
    if task_type == TaskType.creative_media:
        if any(term in text for term in ("video", "storyboard", "render", "gif", "scene")):
            return "studio-director"
        return "creative-artist"
    if task_type == TaskType.review:
        return "security-review"
    if task_type == TaskType.debug and "ci" in text:
        return "fix-ci"
    if task_type == TaskType.coding:
        if any(term in text for term in ("test", "tests", "coverage")):
            return "write-tests"
        if "ci" in text:
            return "fix-ci"
        return "termit-platform-dev"
    return "termit-platform-dev"


def resolve_project_template_ids(task_type: TaskType, input_text: str) -> list[str]:
    text = input_text.lower()
    if task_type == TaskType.online_project:
        return ["online-project-manager", "research-fast"]
    if task_type == TaskType.online_research:
        if any(item in text for item in ("deep", "thorough", "comprehensive")):
            return ["research-deep", "research-fast"]
        return ["research-fast"]
    if task_type == TaskType.creative_media:
        if any(item in text for item in ("video", "storyboard", "render", "scene")):
            return ["studio-director", "creative-artist"]
        return ["creative-artist"]

    templates = ["termit-platform-dev"]
    if any(item in text for item in ("test", "tests", "coverage")):
        templates.append("write-tests")
    if "ci" in text:
        templates.append("fix-ci")
    if any(item in text for item in ("security", "audit", "vulnerability")):
        templates.append("security-review")
    unique: list[str] = []
    for item in templates:
        if item not in unique:
            unique.append(item)
    return unique
