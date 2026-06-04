from __future__ import annotations

import fnmatch
import re
from pathlib import Path


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(content.strip())
    if not match:
        return {}, content.strip()
    meta_raw, body = match.group(1), match.group(2).strip()
    meta: dict[str, str] = {}
    for line in meta_raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class CursorRulesImporter:
    """Import Cursor project rules (.mdc) and AGENTS.md into Termit prompt text."""

    def build_prompt_block(
        self,
        workspace_root: str | Path,
        *,
        active_path: str = "",
        include_all: bool = False,
    ) -> str:
        root = Path(workspace_root).expanduser().resolve()
        if not root.is_dir():
            return ""

        sections: list[str] = []
        rules_dir = root / ".cursor" / "rules"
        if rules_dir.is_dir():
            for path in sorted(rules_dir.glob("*.mdc")):
                block = self._format_mdc_rule(
                    path,
                    active_path=active_path,
                    include_all=include_all,
                )
                if block:
                    sections.append(block)

        agents_md = root / "AGENTS.md"
        if agents_md.is_file():
            body = agents_md.read_text(encoding="utf-8").strip()
            if body:
                sections.append(f"[AGENTS.md]\n{body}")

        return "\n\n".join(sections).strip()

    def merge_into_project_rules(
        self,
        existing_rules: str,
        workspace_root: str | Path,
        *,
        active_path: str = "",
    ) -> str:
        imported = self.build_prompt_block(
            workspace_root,
            active_path=active_path,
            include_all=True,
        )
        if not imported:
            return existing_rules.strip()
        marker = "[Cursor rules import]"
        if marker in existing_rules:
            before, _, after = existing_rules.partition(marker)
            tail = after.split("\n\n[Project rules]", 1)
            project_tail = tail[1] if len(tail) > 1 else ""
            merged = f"{before.strip()}\n\n{marker}\n{imported}".strip()
            if project_tail.strip():
                merged = f"{merged}\n\n[Project rules]\n{project_tail.strip()}"
            return merged.strip()
        if existing_rules.strip():
            return f"{marker}\n{imported}\n\n[Project rules]\n{existing_rules.strip()}".strip()
        return f"{marker}\n{imported}".strip()

    def _format_mdc_rule(self, path: Path, *, active_path: str, include_all: bool = False) -> str:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return ""
        meta, body = _parse_frontmatter(content)
        if not body:
            return ""

        always_apply = _truthy(meta.get("alwaysApply", "false"))
        globs = meta.get("globs", "").strip()
        if not include_all:
            if globs and active_path:
                patterns = [item.strip() for item in globs.split(",") if item.strip()]
                if patterns and not any(fnmatch.fnmatch(active_path, pattern) for pattern in patterns):
                    return ""
            elif not always_apply and not globs:
                return ""

        title = meta.get("description") or path.stem
        scope = ""
        if globs:
            scope = f" (globs: {globs})"
        return f"[Cursor rule: {title}{scope}]\n{body}"
