from __future__ import annotations

from pathlib import Path


class RepoMapService:
    _SKIP_DIRS = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
    }
    _KEY_FILES = {
        "README.md",
        "README",
        "pyproject.toml",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "Makefile",
        "docker-compose.yml",
    }

    def __init__(self, root_path: str = ".", max_dirs: int = 40) -> None:
        self.root = Path(root_path).resolve()
        self.max_dirs = max(5, max_dirs)

    def build_summary(self, *, path_prefix: str = "") -> str:
        prefix = path_prefix.strip().replace("\\", "/")
        scan_root = self.root / prefix if prefix else self.root
        if not scan_root.exists():
            scan_root = self.root

        dirs: list[str] = []
        ext_counts: dict[str, int] = {}
        key_files: list[str] = []

        for path in sorted(scan_root.rglob("*")):
            rel = str(path.relative_to(self.root)).replace("\\", "/")
            if prefix and not rel.startswith(prefix):
                continue
            if any(part in self._SKIP_DIRS for part in path.parts):
                continue
            if path.is_dir():
                depth = len(Path(rel).parts)
                base_depth = len(Path(prefix).parts) if prefix else 0
                if depth - base_depth <= 2 and len(dirs) < self.max_dirs:
                    dirs.append(rel + "/")
                continue
            ext = path.suffix.lower() or "(no ext)"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            if path.name in self._KEY_FILES and path.name not in key_files:
                key_files.append(rel)

        readme_snippet = self._readme_snippet(key_files)
        lines = [
            "[Repo map] Workspace structure summary:",
            f"root: {self.root}",
        ]
        if prefix:
            lines.append(f"scope: {prefix}")
        if dirs:
            lines.append("")
            lines.append("Top directories:")
            lines.extend(f"- {item}" for item in dirs[: self.max_dirs])
        if ext_counts:
            lines.append("")
            lines.append("File types:")
            for ext, count in sorted(ext_counts.items(), key=lambda item: item[1], reverse=True)[:12]:
                lines.append(f"- {ext}: {count}")
        if key_files:
            lines.append("")
            lines.append("Key files:")
            lines.extend(f"- {item}" for item in key_files[:10])
        if readme_snippet:
            lines.append("")
            lines.append("README excerpt:")
            lines.append(readme_snippet)
        return "\n".join(lines).strip()

    def _readme_snippet(self, key_files: list[str]) -> str:
        readme_path = next((item for item in key_files if item.lower().endswith("readme.md")), None)
        if readme_path is None:
            candidate = self.root / "README.md"
            if candidate.exists():
                readme_path = "README.md"
            else:
                return ""
        try:
            text = (self.root / readme_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        snippet = text.strip().splitlines()[:12]
        body = "\n".join(snippet)
        if len(body) > 900:
            body = body[:897] + "..."
        return body
