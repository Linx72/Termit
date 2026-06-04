"""Cursor-like build workflow: plan and research before creating files."""

from __future__ import annotations

import re


_BUILD_HINTS = re.compile(
    r"(?i)\b("
    r"сайт|website|web\s*app|landing|лендинг|программ|приложен|"
    r"react|vite|next\.?js|vue|angular|html|css|frontend|backend|api|"
    r"fix|bug|refactor|implement|feature|тест|test|"
    r"create\s+(a\s+)?(app|site|program|website|api)|"
    r"сделай|создай|собери|напиши|исправь|добавь|реализуй"
    r")\b"
)


class BuildWorkflowService:
    """Detect full-stack / web build tasks and enrich agent input with phased workflow."""

    @staticmethod
    def is_build_task(text: str) -> bool:
        stripped = (text or "").strip()
        if len(stripped) < 8:
            return False
        return bool(_BUILD_HINTS.search(stripped))

    @staticmethod
    def enrich_agent_input(
        user_input: str,
        *,
        execution_mode: str = "local",
        workspace: str = "",
        ssh_label: str = "",
    ) -> str:
        mode = (execution_mode or "local").strip().lower()
        workspace_line = workspace.strip() or "(не выбран / not set)"
        target_line = ssh_label.strip() if mode == "ssh" and ssh_label.strip() else workspace_line

        if mode == "ssh":
            target_block = (
                f"Цель файлов и команд: **SSH** → {target_line}\n"
                f"Local workspace (retrieval only): {workspace_line}"
            )
        elif mode == "hybrid":
            target_block = (
                f"Файлы/команды: local `{workspace_line}` + online (web_search, browser_*).\n"
                "Сначала исследование и preview в браузере, затем патчи в workspace."
            )
        elif mode == "online":
            target_block = "Режим online: web_search + browser_* для research и preview."
        else:
            target_block = f"Local workspace: `{workspace_line}`"

        return (
            "Ты Termit Builder в режиме Cursor-like one-window.\n"
            "Выполни задачу **по фазам** и отчитывайся в ленте событий после каждой фазы.\n\n"
            f"{target_block}\n\n"
            "## Фаза 1 — PLAN (без apply_patch)\n"
            "- Определи стек (Vite/React/TS по умолчанию для сайта).\n"
            "- Список страниц/компонентов, структура каталогов, verify-команды из package.json.\n"
            "- Краткий план в ответе; **не создавай файлы** до явного перехода к фазе 2.\n\n"
            "## Фаза 2 — RESEARCH (online/hybrid)\n"
            "- Если нужны API/дизайн-паттерны — web_search и browser_snapshot.\n"
            "- Зафиксируй решения в 3–5 пунктах.\n\n"
            "## Фаза 3 — SCAFFOLD\n"
            "- Создай минимальный каркас (package.json, vite.config, src/, index.html).\n"
            "- После scaffold — execute_command для install deps при необходимости.\n\n"
            "## Фаза 4 — IMPLEMENT\n"
            "- Мелкие apply_patch; после каждого значимого блока — verify.\n\n"
            "## Фаза 5 — VERIFY & PREVIEW\n"
            "- npm test / lint / build (или эквивалент из package.json).\n"
            "- hybrid/online: browser_navigate на dev URL и snapshot UI.\n\n"
            "## Фаза 6 — REPORT\n"
            "- Итог: что сделано, как запустить, что проверить дальше.\n\n"
            "---\n"
            f"Задача пользователя:\n{user_input.strip()}"
        )
