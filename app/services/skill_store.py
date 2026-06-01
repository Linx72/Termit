from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    name: str
    description: str
    content: str
    path: str


class SkillStore:
    def __init__(self, root_path: str) -> None:
        self.root = Path(root_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[SkillRecord]:
        records: list[SkillRecord] = []
        for skill_dir in sorted(self.root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            content = skill_file.read_text(encoding="utf-8")
            name, description = self._parse_frontmatter(content, skill_dir.name)
            records.append(
                SkillRecord(
                    skill_id=skill_dir.name,
                    name=name,
                    description=description,
                    content=content,
                    path=str(skill_file),
                )
            )
        return records

    def get_skill(self, skill_id: str) -> SkillRecord | None:
        for item in self.list_skills():
            if item.skill_id == skill_id:
                return item
        return None

    def build_prompt_block(self, skill_ids: list[str]) -> str:
        if not skill_ids:
            return ""
        blocks: list[str] = ["[Mounted agent skills]"]
        for skill_id in skill_ids:
            skill = self.get_skill(skill_id)
            if skill is None:
                continue
            blocks.append(f"## Skill: {skill.name} ({skill.skill_id})")
            blocks.append(skill.content.strip())
            blocks.append("")
        return "\n".join(blocks).strip()

    @staticmethod
    def _parse_frontmatter(content: str, fallback_name: str) -> tuple[str, str]:
        name = fallback_name.replace("-", " ").title()
        description = ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                front = parts[1]
                for line in front.splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip()
        return name, description
