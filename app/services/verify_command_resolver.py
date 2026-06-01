from __future__ import annotations

from pathlib import Path


def resolve_verify_command(root_path: str, configured: str) -> str:
    """Return verify command: explicit config wins, else repo heuristics."""
    explicit = configured.strip()
    if explicit:
        return explicit

    root = Path(root_path).resolve()
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "tests").is_dir():
        return "python3 -m unittest discover -s tests -q"
    if (root / "package.json").exists():
        return "npm test --if-present"
    if (root / "go.mod").exists():
        return "go test ./..."
    if (root / "Cargo.toml").exists():
        return "cargo test"
    return ""
