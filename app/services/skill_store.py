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
    def __init__(self, root_path: str, *, inject_max_chars: int = 4000) -> None:
        self.root = Path(root_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._inject_max_chars = max(500, inject_max_chars)
        self._cache: list[SkillRecord] | None = None
        self._cache_signature: float = 0.0

    def list_skills(self) -> list[SkillRecord]:
        self._maybe_refresh()
        return list(self._cache or [])

    def get_skill(self, skill_id: str) -> SkillRecord | None:
        self._maybe_refresh()
        for item in self._cache or []:
            if item.skill_id == skill_id:
                return item
        return None

    def build_prompt_block(
        self,
        skill_ids: list[str],
        *,
        full_body: bool = False,
        full_body_skill_ids: frozenset[str] | None = None,
    ) -> str:
        if not skill_ids:
            return ""
        blocks: list[str] = ["[Mounted agent skills]"]
        for skill_id in skill_ids:
            skill = self.get_skill(skill_id)
            if skill is None:
                continue
            use_full = full_body or (
                full_body_skill_ids is not None and skill_id in full_body_skill_ids
            )
            blocks.append(self._format_skill_block(skill, full_body=use_full))
            blocks.append("")
        return "\n".join(blocks).strip()

    def build_discovery_block(self, max_items: int = 50) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["[Available agent skills — invoke_skill to load full instructions]"]
        for item in skills[:max(1, max_items)]:
            desc = item.description or item.name
            lines.append(f"- {item.skill_id}: {desc}")
        return "\n".join(lines)

    def skill_body(self, skill: SkillRecord) -> str:
        return self._body_without_frontmatter(skill.content)

    def _format_skill_block(self, skill: SkillRecord, *, full_body: bool) -> str:
        body = self._body_without_frontmatter(skill.content)
        header = f"## Skill: {skill.name} ({skill.skill_id})"
        if full_body or len(body) <= self._inject_max_chars:
            return f"{header}\n{skill.content.strip()}"

        preview = body[: self._inject_max_chars].rstrip()
        if not preview.endswith("…"):
            preview = preview + "…"
        desc_line = f"Description: {skill.description}" if skill.description else ""
        path_hint = f"invoke_skill skill_id=\"{skill.skill_id}\" or read_file path=\"{skill.path}\""
        truncated_note = (
            f"[Skill body truncated at {self._inject_max_chars} chars. "
            f"Full instructions: {path_hint}]"
        )
        parts = [header]
        if desc_line:
            parts.append(desc_line)
        parts.append(truncated_note)
        parts.append(preview)
        return "\n".join(parts)

    def _maybe_refresh(self) -> None:
        signature = self._directory_signature()
        if self._cache is not None and signature == self._cache_signature:
            return
        self._cache = self._load_skills()
        self._cache_signature = signature

    def _directory_signature(self) -> float:
        if not self.root.is_dir():
            return 0.0
        latest = 0.0
        try:
            latest = max(latest, self.root.stat().st_mtime)
        except OSError:
            pass
        for skill_dir in self.root.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            try:
                latest = max(latest, skill_file.stat().st_mtime)
            except OSError:
                continue
        return latest

    def _load_skills(self) -> list[SkillRecord]:
        records: list[SkillRecord] = []
        if not self.root.is_dir():
            return records
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

    @staticmethod
    def _body_without_frontmatter(content: str) -> str:
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content.strip()

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
