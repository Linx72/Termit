#!/usr/bin/env python3
"""Rebuild per-project Cursor agent prompt and skill archive from agent transcripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Typical user themes (RU + EN) mined for the generated prompt appendix.
_THEME_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("do_all", re.compile(r"do\s*all|track\s*b|сделай\s*вс[её]|вс[её]\s*сразу", re.I)),
    ("platform", re.compile(r"platform|parity|mcp|skill|hook", re.I)),
    ("agent_loop", re.compile(r"agent|tool\s*loop|orchestrat|run\b|sse|resume", re.I)),
    ("finetune", re.compile(r"finetune|qlora|adapter|training", re.I)),
    ("eval", re.compile(r"eval|regression|gate|scenario", re.I)),
    ("desktop", re.compile(r"desktop|monaco|wizard|vscode", re.I)),
    ("verify", re.compile(r"провер|smoke|unittest|тест", re.I)),
    ("russian", re.compile(r"русск|bilingual|i18n", re.I)),
]

_PATH_KEYS = ("path", "target_directory", "target_notebook")
_TOOL_PATH_RE = re.compile(
    r"(?:^|/)(app|clients|tests|scripts|data|\.cursor)/[^\s\"']+"
)


def _slugify_workspace(root: Path) -> str:
    name = root.name or "project"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "project"


def _default_transcripts_dir(project_root: Path) -> Path:
    home = Path.home()
    candidates = [
        home / ".cursor" / "projects" / f"{project_root.as_posix().replace('/', '-').lstrip('-')}" / "agent-transcripts",
        home / ".cursor" / "projects" / project_root.name / "agent-transcripts",
    ]
    # Cursor encodes path: Users-orosam-Projects-Termit
    encoded = "-".join(project_root.resolve().parts).lstrip("-")
    candidates.insert(0, home / ".cursor" / "projects" / encoded / "agent-transcripts")
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def _rel_project_path(raw: str, project_root: Path) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    root_s = str(project_root.resolve())
    if root_s in text:
        return text.split(root_s, 1)[-1].lstrip("/\\")
    m = _TOOL_PATH_RE.search(text.replace("\\", "/"))
    if m:
        return m.group(0).lstrip("/")
    return None


def _extract_user_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text") or ""
        if "<user_query>" in text:
            m = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.S)
            if m:
                parts.append(m.group(1).strip())
                continue
        parts.append(text.strip())
    return "\n".join(p for p in parts if p)


@dataclass
class SessionDigest:
    session_id: str
    user_turns: int = 0
    sample_queries: list[str] = field(default_factory=list)
    touched_paths: Counter[str] = field(default_factory=Counter)


@dataclass
class ArchiveDigest:
    project_root: Path
    transcripts_dir: Path
    parent_sessions: int = 0
    user_turns: int = 0
    path_counts: Counter[str] = field(default_factory=Counter)
    theme_counts: Counter[str] = field(default_factory=Counter)
    recent_queries: list[str] = field(default_factory=list)
    sessions: list[SessionDigest] = field(default_factory=list)


def collect_transcript_digest(
    transcripts_dir: Path,
    project_root: Path,
    *,
    max_recent_queries: int = 12,
    max_sample_per_session: int = 2,
) -> ArchiveDigest:
    digest = ArchiveDigest(project_root=project_root, transcripts_dir=transcripts_dir)
    if not transcripts_dir.is_dir():
        return digest

    for session_dir in sorted(transcripts_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        session_id = session_dir.name
        main_file = session_dir / f"{session_id}.jsonl"
        if not main_file.is_file():
            continue
        digest.parent_sessions += 1
        session = SessionDigest(session_id=session_id)

        for line in main_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = row.get("role")
            message = row.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue

            if role == "user":
                text = _extract_user_text(content)
                if not text:
                    continue
                digest.user_turns += 1
                session.user_turns += 1
                if len(session.sample_queries) < max_sample_per_session:
                    snippet = re.sub(r"\s+", " ", text)[:240]
                    session.sample_queries.append(snippet)
                for theme, pat in _THEME_PATTERNS:
                    if pat.search(text):
                        digest.theme_counts[theme] += 1

            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                inp = block.get("input")
                if not isinstance(inp, dict):
                    continue
                for key in _PATH_KEYS:
                    val = inp.get(key)
                    if isinstance(val, str):
                        rel = _rel_project_path(val, project_root)
                        if rel:
                            digest.path_counts[rel] += 1
                            session.touched_paths[rel] += 1
                pattern = inp.get("pattern")
                if isinstance(pattern, str):
                    rel = _rel_project_path(pattern, project_root)
                    if rel:
                        digest.path_counts[rel] += 1

        if session.user_turns:
            digest.sessions.append(session)
            for q in session.sample_queries:
                if q not in digest.recent_queries:
                    digest.recent_queries.append(q)
                if len(digest.recent_queries) >= max_recent_queries:
                    break

    digest.recent_queries = digest.recent_queries[:max_recent_queries]
    return digest


def _read_phase_hint(project_root: Path) -> str:
    skill = project_root / ".cursor" / "skills" / "termit-agent" / "reference.md"
    if skill.is_file():
        text = skill.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"\*\*Следующий фокус:\*\*\s*(.+)", text)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m = re.search(
            r"\|\s*3\s+Desktop UX\s*\|\s*([^|]+)\|\s*([^|]+)\|",
            text,
        )
        if m:
            status, focus = (m.group(1).strip(), m.group(2).strip())
            if status or focus:
                return f"фаза 3 (desktop UX): {status} — {focus}".strip(" —")
    master = project_root / "PROJECT_TASK_PROMPT_RU.md"
    if master.is_file():
        return "фазы 0–2 в основном закрыты → фаза 3 desktop UX + фаза 4 eval/training loop (см. PROJECT_TASK_PROMPT_RU.md)"
    return "см. README и START_HERE_RU.md"


def _one_liner_from_baseline(project_root: Path) -> str:
    baseline = (
        project_root
        / ".cursor"
        / "skills"
        / "termit-agent"
        / "archive"
        / "reference-sessions-baseline.md"
    )
    if baseline.is_file():
        m = re.search(r"One-liner[^>]*>\s*(.+)", baseline.read_text(encoding="utf-8"))
        if m:
            return m.group(1).strip()
    return (
        "локальный AI-оркестратор с очередью агентов, eval/finetune и Cursor-like клиентами; "
        "end-to-end, самопроверка, ответы на русском."
    )


def render_generated_archive(digest: ArchiveDigest, *, generated_at: str) -> str:
    lines = [
        "# Архив сессий — автогенерация из agent-transcripts",
        "",
        f"> Сгенерировано: `{generated_at}`. Источник: `{digest.transcripts_dir}`.",
        "> Не править вручную — пересобрать: `python3 scripts/rebuild_cursor_agent_context.py`.",
        "",
        "## Статистика",
        "",
        f"| Метрика | Значение |",
        f"|---------|----------|",
        f"| Parent-сессий | {digest.parent_sessions} |",
        f"| User-ходов | {digest.user_turns} |",
        f"| Каталог транскриптов | `{digest.transcripts_dir}` |",
        "",
        "## Темы запросов (эвристика)",
        "",
    ]
    if digest.theme_counts:
        for theme, count in digest.theme_counts.most_common():
            lines.append(f"- **{theme}**: {count}")
    else:
        lines.append("- _(нет данных — транскрипты пусты или недоступны)_")

    lines.extend(["", "## Частые пути в tool_use", ""])
    if digest.path_counts:
        for path, count in digest.path_counts.most_common(20):
            lines.append(f"- `{path}` — {count}")
    else:
        lines.append("- _(нет путей в пределах репозитория)_")

    lines.extend(["", "## Недавние формулировки пользователя", ""])
    if digest.recent_queries:
        for i, q in enumerate(digest.recent_queries, 1):
            lines.append(f"{i}. {q}")
    else:
        lines.append("_(пусто)_")

    lines.extend(
        [
            "",
            "## One-liner для новых чатов",
            "",
            f"> {_one_liner_from_baseline(digest.project_root)}",
            "",
        ]
    )
    return "\n".join(lines)


def render_new_agent_prompt(digest: ArchiveDigest, *, generated_at: str) -> str:
    phase = _read_phase_hint(digest.project_root)
    one_liner = _one_liner_from_baseline(digest.project_root)
    top_paths = [p for p, _ in digest.path_counts.most_common(8)]
    top_themes = [t for t, _ in digest.theme_counts.most_common(6)]

    lines = [
        "---",
        "description: Промпт для нового Cursor-агента в этом репозитории (автогенерация из архива сессий)",
        "alwaysApply: false",
        "---",
        "",
        "# Новый агент — контекст проекта",
        "",
        f"_Обновлено: {generated_at}. Parent-сессий в архиве: {digest.parent_sessions}, user-ходов: {digest.user_turns}._",
        "",
        "## Кто ты",
        "",
        f"**One-liner:** {one_liner}",
        "",
        "## Северная звезда",
        "",
        "Termit.app → репозиторий → задача → агент читает код, правит, гоняет тесты, отчитывается без ручного копирования в чат.",
        "",
        "## Текущий вектор",
        "",
        phase,
        "",
        "## Не переизобретать",
        "",
        "- FastAPI backend, agent queue, SQLite runs, SSE timeline",
        "- Tool loop 2.0, verify, resume, human confirm, multi-agent",
        "- Platform API: MCP, skills, hooks, guardrails (`/api/platform/*`)",
        "- Clients: `termit-client`, `termit-desktop`, VS Code extension",
        "- Eval/finetune pipeline + `eval_ci_gate` в CI",
        "",
        "## Стиль работы",
        "",
        "- Ответы на **русском** (см. `respond-in-russian.mdc`)",
        "- Минимальный diff; «do all» / Track B — блок целиком",
        "- **Проверяй сам:** unittest + smoke `:8765` (`verify-after-serious-changes.mdc`)",
        "- Итог с фактами: passed/failed, HTTP-коды",
        "",
        "## Master plan",
        "",
        "- `PROJECT_TASK_PROMPT_RU.md`",
        "- `PLATFORM_PARITY_PLAN_RU.md`",
        "- Skill: `.cursor/skills/termit-agent/SKILL.md`",
        "",
    ]

    if top_themes:
        lines.extend(["## Частые темы из архива чатов", ""])
        for t in top_themes:
            lines.append(f"- {t}")
        lines.append("")

    if top_paths:
        lines.extend(["## Горячие пути в прошлых сессиях", ""])
        for p in top_paths:
            lines.append(f"- `{p}`")
        lines.append("")

    if digest.recent_queries:
        lines.extend(["## Примеры недавних запросов", ""])
        for q in digest.recent_queries[:6]:
            lines.append(f"- {q}")
        lines.append("")

    lines.extend(
        [
            "## Артефакты архива",
            "",
            "- Снимок milestones: `.cursor/skills/termit-agent/archive/reference-sessions-baseline.md`",
            "- Автосводка сессий: `.cursor/skills/termit-agent/archive/generated-from-transcripts.md`",
            f"- Промпт этого проекта: `.cursor/agent/projects/{_slugify_workspace(digest.project_root)}/new-agent-prompt.md`",
            "",
        ]
    )
    return "\n".join(lines)


def _update_skill_archive_readme(project_root: Path, generated_at: str) -> None:
    readme = project_root / ".cursor" / "skills" / "termit-agent" / "archive" / "README.md"
    if not readme.is_file():
        return
    text = readme.read_text(encoding="utf-8")
    row = (
        f"| `generated-from-transcripts.md` | {generated_at[:10]} | "
        "Автосводка из `agent-transcripts` (скрипт rebuild) |"
    )
    if "generated-from-transcripts.md" in text:
        text = re.sub(
            r"\| `generated-from-transcripts\.md`[^\n]+\n",
            row + "\n",
            text,
            count=1,
        )
    elif "##" in text or "| Файл |" in text:
        text = text.replace(
            "| `reference-sessions-baseline.md`",
            row + "\n| `reference-sessions-baseline.md`",
            1,
        )
    readme.write_text(text, encoding="utf-8")


def rebuild(project_root: Path, transcripts_dir: Path | None = None) -> dict[str, Path]:
    project_root = project_root.resolve()
    transcripts_dir = (transcripts_dir or _default_transcripts_dir(project_root)).resolve()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    digest = collect_transcript_digest(transcripts_dir, project_root)
    slug = _slugify_workspace(project_root)

    out_agent_dir = project_root / ".cursor" / "agent" / "projects" / slug
    out_agent_dir.mkdir(parents=True, exist_ok=True)

    archive_generated = (
        project_root
        / ".cursor"
        / "skills"
        / "termit-agent"
        / "archive"
        / "generated-from-transcripts.md"
    )
    archive_generated.parent.mkdir(parents=True, exist_ok=True)
    archive_generated.write_text(
        render_generated_archive(digest, generated_at=generated_at),
        encoding="utf-8",
    )

    per_project_prompt = out_agent_dir / "new-agent-prompt.md"
    per_project_prompt.write_text(
        render_new_agent_prompt(digest, generated_at=generated_at),
        encoding="utf-8",
    )

    # Symlink-style canonical copy at repo root for quick @-mention
    canonical = project_root / ".cursor" / "NEW_AGENT_PROMPT.md"
    canonical.write_text(per_project_prompt.read_text(encoding="utf-8"), encoding="utf-8")

    _update_skill_archive_readme(project_root, generated_at)

    # Pointer in reference.md
    ref = project_root / ".cursor" / "skills" / "termit-agent" / "reference.md"
    if ref.is_file():
        text = ref.read_text(encoding="utf-8")
        marker = "## Архив skill"
        addon = (
            "\n\nАвтосводка из чатов (пересборка при `sessionEnd`): "
            "[archive/generated-from-transcripts.md](archive/generated-from-transcripts.md). "
            f"Промпт нового агента: [../../agent/projects/{slug}/new-agent-prompt.md]"
            f"(../../agent/projects/{slug}/new-agent-prompt.md)."
        )
        if "generated-from-transcripts.md" not in text and marker in text:
            text = text.replace(marker, marker + addon, 1)
            ref.write_text(text, encoding="utf-8")

    return {
        "archive": archive_generated,
        "per_project_prompt": per_project_prompt,
        "canonical_prompt": canonical,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Корень репозитория (по умолчанию cwd)",
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        default=None,
        help="Каталог agent-transcripts (по умолчанию ~/.cursor/projects/...)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        outputs = rebuild(args.project_root, args.transcripts_dir)
    except OSError as exc:
        print(f"rebuild failed: {exc}", file=sys.stderr)
        return 1

    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
