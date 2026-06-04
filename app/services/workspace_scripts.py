from __future__ import annotations

import json
from pathlib import Path


def read_package_scripts(root_path: str) -> dict[str, str]:
    root = Path(root_path).resolve()
    pkg = root / "package.json"
    if not pkg.is_file():
        return {}
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return {}
    return {str(key): str(value) for key, value in scripts.items()}


def resolve_verify_command(root_path: str, configured: str) -> str:
    """Return verify command: explicit config wins, else repo heuristics."""
    explicit = configured.strip()
    if explicit:
        return explicit

    root = Path(root_path).resolve()
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "tests").is_dir():
        return "python3 -m unittest discover -s tests -q"

    npm_verify = _npm_verify_command(root)
    if npm_verify:
        return npm_verify

    if (root / "go.mod").exists():
        return "go test ./..."
    if (root / "Cargo.toml").exists():
        return "cargo test"
    return ""


def resolve_dev_server_command(root_path: str) -> str:
    scripts = read_package_scripts(root_path)
    for key in ("dev", "start", "serve"):
        if key in scripts:
            return f"npm run {key}"
    return ""


def workspace_script_hints(root_path: str) -> dict[str, str]:
    scripts = read_package_scripts(root_path)
    hints: dict[str, str] = {}
    verify = resolve_verify_command(root_path, "")
    if verify:
        hints["verify"] = verify
    dev = resolve_dev_server_command(root_path)
    if dev:
        hints["dev"] = dev
    if "lint" in scripts:
        hints["lint"] = "npm run lint"
    if "build" in scripts:
        hints["build"] = "npm run build"
    if "test" in scripts and "verify" not in hints:
        hints["test"] = "npm test"
    return hints


def _npm_verify_command(root: Path) -> str:
    scripts = read_package_scripts(str(root))
    if not scripts:
        if (root / "package.json").exists():
            return "npm test --if-present"
        return ""

    parts: list[str] = []
    for key in ("test", "test:unit", "test:ci"):
        if key in scripts:
            parts.append(f"npm run {key}" if key != "test" else "npm test")
            break
    if "lint" in scripts:
        parts.append("npm run lint")
    if "build" in scripts:
        parts.append("npm run build")
    if parts:
        return " && ".join(parts)
    return "npm test --if-present"
