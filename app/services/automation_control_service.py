"""do_all_automatic toggles: .env persistence + live scheduler control."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from app.core.config import Settings, get_settings
from app.services.agent_maintenance_scheduler_service import AgentMaintenanceSchedulerService
from app.services.agent_schedule_service import AgentScheduleService
from app.services.daily_improvement_scheduler_service import DailyImprovementSchedulerService
from app.services.env_file_service import EnvFileService, parse_bool
from app.services.stage1_scheduler_service import Stage1SchedulerService


@dataclass(frozen=True)
class AutomationToggleSpec:
    toggle_id: str
    env_key: str
    label_ru: str
    label_en: str
    description_ru: str
    description_en: str
    cron_marker: Optional[str] = None


TOGGLE_SPECS: tuple[AutomationToggleSpec, ...] = (
    AutomationToggleSpec(
        toggle_id="stage1_schedule",
        env_key="TERMIT_STAGE1_SCHEDULE_ENABLED",
        label_ru="Finetune Stage1 (еженедельно)",
        label_en="Finetune Stage1 (weekly)",
        description_ru="Встроенный пайплайн Stage1 по расписанию (UTC).",
        description_en="Built-in weekly Stage1 finetune pipeline (UTC).",
    ),
    AutomationToggleSpec(
        toggle_id="daily_improvement",
        env_key="TERMIT_DAILY_IMPROVEMENT_ENABLED",
        label_ru="Daily improvement",
        label_en="Daily improvement",
        description_ru="Ночной цикл улучшений: DLQ, eval probe, finetune сигналы.",
        description_en="Nightly improvement loop: DLQ, eval probe, finetune signals.",
    ),
    AutomationToggleSpec(
        toggle_id="agent_schedules",
        env_key="TERMIT_AGENT_SCHEDULES_ENABLED",
        label_ru="Расписания агентов",
        label_en="Agent schedules",
        description_ru="Cron-задачи агентов из platform API.",
        description_en="Cron-driven agent runs from platform API.",
    ),
    AutomationToggleSpec(
        toggle_id="agent_maintenance",
        env_key="TERMIT_AGENT_MAINTENANCE_ENABLED",
        label_ru="Обслуживание agent runs",
        label_en="Agent run maintenance",
        description_ru="Очистка старых run'ов и снимки метрик.",
        description_en="Cleanup old runs and metrics snapshots.",
    ),
    AutomationToggleSpec(
        toggle_id="retrieval_auto_reindex",
        env_key="TERMIT_RETRIEVAL_AUTO_REINDEX",
        label_ru="Авто-reindex retrieval",
        label_en="Retrieval auto-reindex",
        description_ru="Фоновое обновление индекса при изменениях репо.",
        description_en="Background reindex when the repo changes.",
    ),
    AutomationToggleSpec(
        toggle_id="finetune_auto_capture",
        env_key="TERMIT_FINETUNE_AUTO_CAPTURE_SIGNALS",
        label_ru="Захват training signals",
        label_en="Training signal capture",
        description_ru="Автосбор сигналов для finetune из agent/chat.",
        description_en="Auto-capture finetune signals from agent/chat.",
    ),
    AutomationToggleSpec(
        toggle_id="auto_start_ollama",
        env_key="TERMIT_AUTO_START_OLLAMA",
        label_ru="Старт Ollama при запуске API",
        label_en="Start Ollama on API boot",
        description_ru="Применяется после перезапуска сервера Termit.",
        description_en="Takes effect after restarting the Termit API.",
    ),
    AutomationToggleSpec(
        toggle_id="weekly_eval_cron",
        env_key="",
        label_ru="Weekly eval (crontab)",
        label_en="Weekly eval (crontab)",
        description_ru="Внешний cron: weekly closed loop (пн 04:00) — eval + shadow + orch gates.",
        description_en="External cron: weekly closed loop (Mon 04:00) — eval, shadow, orch gates.",
        cron_marker="# termit-weekly-eval",
    ),
    AutomationToggleSpec(
        toggle_id="daily_improvement_cron",
        env_key="",
        label_ru="Daily improvement (crontab)",
        label_en="Daily improvement (crontab)",
        description_ru="Внешний cron из do_all_automatic (02:05).",
        description_en="External cron from do_all_automatic (02:05).",
        cron_marker="# termit-daily-improvement",
    ),
    AutomationToggleSpec(
        toggle_id="training_loop_cron",
        env_key="",
        label_ru="Training loop (crontab)",
        label_en="Training loop (crontab)",
        description_ru="Внешний cron: training_loop_weekly.sh (вс 04:00).",
        description_en="External cron: training_loop_weekly.sh (Sun 04:00).",
        cron_marker="# termit-training-loop-weekly",
    ),
    AutomationToggleSpec(
        toggle_id="quarterly_capability_cron",
        env_key="",
        label_ru="Quarterly capability (crontab)",
        label_en="Quarterly capability (crontab)",
        description_ru="Внешний cron: quarterly_capability.sh (1-е Jan/Apr/Jul/Oct 05:00).",
        description_en="External cron: quarterly_capability.sh (1st Jan/Apr/Jul/Oct 05:00).",
        cron_marker="# termit-quarterly-capability",
    ),
)


def _toggle_enabled(settings: Settings, spec: AutomationToggleSpec) -> bool:
    mapping = {
        "stage1_schedule": settings.stage1_schedule_enabled,
        "daily_improvement": settings.daily_improvement_enabled,
        "agent_schedules": settings.agent_schedules_enabled,
        "agent_maintenance": settings.agent_maintenance_enabled,
        "retrieval_auto_reindex": settings.retrieval_auto_reindex,
        "finetune_auto_capture": settings.finetune_auto_capture_signals,
        "auto_start_ollama": settings.auto_start_ollama,
    }
    return bool(mapping.get(spec.toggle_id, False))


def _cron_installed(marker: str) -> bool:
    try:
        proc = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    return marker in (proc.stdout or "")


def _remove_cron_marker(marker: str) -> bool:
    try:
        proc = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return True
    lines = [line for line in (proc.stdout or "").splitlines() if marker not in line]
    payload = "\n".join(lines).strip()
    if payload:
        payload += "\n"
    install = subprocess.run(
        ["crontab", "-"],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return install.returncode == 0


def _install_cron_line(marker: str, schedule: str, command: str) -> bool:
    line = f"{schedule} {command} {marker}"
    try:
        proc = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    existing = proc.stdout if proc.returncode == 0 else ""
    if marker in existing:
        return True
    body = existing.rstrip()
    if body:
        body += "\n"
    body += line + "\n"
    install = subprocess.run(
        ["crontab", "-"],
        input=body,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return install.returncode == 0


class AutomationControlService:
    def __init__(
        self,
        *,
        env_service: Optional[EnvFileService] = None,
        stage1_scheduler: Optional[Stage1SchedulerService] = None,
        daily_scheduler: Optional[DailyImprovementSchedulerService] = None,
        maintenance_scheduler: Optional[AgentMaintenanceSchedulerService] = None,
        agent_schedule_service: Optional[AgentScheduleService] = None,
        project_root: Optional[str] = None,
    ) -> None:
        self._env = env_service or EnvFileService()
        self._stage1 = stage1_scheduler
        self._daily = daily_scheduler
        self._maintenance = maintenance_scheduler
        self._agent_schedules = agent_schedule_service
        self._root = (project_root or os.getenv("TERMIT_PROJECT_ROOT", ".")).strip()

    def snapshot(self) -> dict[str, object]:
        settings = get_settings()
        toggles: list[dict[str, object]] = []
        for spec in TOGGLE_SPECS:
            if spec.cron_marker:
                enabled = _cron_installed(spec.cron_marker)
            else:
                enabled = _toggle_enabled(settings, spec)
            toggles.append(
                {
                    "toggle_id": spec.toggle_id,
                    "env_key": spec.env_key or None,
                    "label_ru": spec.label_ru,
                    "label_en": spec.label_en,
                    "description_ru": spec.description_ru,
                    "description_en": spec.description_en,
                    "enabled": enabled,
                    "requires_restart": spec.toggle_id == "auto_start_ollama",
                }
            )
        automatic_mode_enabled = all(item["enabled"] for item in toggles if item["toggle_id"] not in {"auto_start_ollama"})
        return {
            "env_path": str(self._env.path),
            "automatic_mode_enabled": automatic_mode_enabled,
            "toggles": toggles,
            "schedulers": self._scheduler_status(),
        }

    def apply(self, updates: dict[str, bool]) -> dict[str, object]:
        applied: list[str] = []
        restart_recommended = False
        for spec in TOGGLE_SPECS:
            if spec.toggle_id not in updates:
                continue
            enabled = bool(updates[spec.toggle_id])
            if spec.cron_marker:
                if enabled:
                    ok = self._install_cron_for(spec)
                else:
                    ok = _remove_cron_marker(spec.cron_marker)
                if ok:
                    applied.append(spec.toggle_id)
                continue
            self._env.set_key(spec.env_key, "true" if enabled else "false")
            self._apply_runtime(spec.toggle_id, enabled)
            applied.append(spec.toggle_id)
            if spec.toggle_id == "auto_start_ollama":
                restart_recommended = True
        result = self.snapshot()
        result["applied"] = applied
        result["restart_recommended"] = restart_recommended
        return result

    def set_automatic_mode(self, enabled: bool) -> dict[str, object]:
        payload = {spec.toggle_id: enabled for spec in TOGGLE_SPECS}
        return self.apply(payload)

    def _install_cron_for(self, spec: AutomationToggleSpec) -> bool:
        root = os.path.abspath(self._root)
        venv = f"{root}/.venv/bin/activate"
        log_dir = "$HOME/Library/Logs" if sys.platform == "darwin" else "$HOME"
        if spec.toggle_id == "weekly_eval_cron":
            cmd = (
                f"cd {root} && source {venv} && {root}/scripts/weekly_closed_loop.sh "
                f">> {log_dir}/termit-weekly-closed-loop.log 2>&1"
            )
            return _install_cron_line(spec.cron_marker or "", "0 4 * * 1", cmd)
        if spec.toggle_id == "daily_improvement_cron":
            cmd = (
                f"cd {root} && source {venv} && {root}/scripts/daily_improvement.sh "
                f">> {log_dir}/termit-daily-improvement.log 2>&1"
            )
            return _install_cron_line(spec.cron_marker or "", "5 2 * * *", cmd)
        if spec.toggle_id == "training_loop_cron":
            cmd = (
                f"cd {root} && source {venv} && "
                f"TERMIT_WEEKLY_TRAINING_LOOP=true TERMIT_EVAL_AUTO_PROMOTE_BASELINE=true "
                f"{root}/scripts/training_loop_weekly.sh "
                f">> {log_dir}/termit-training-loop-weekly.cron.log 2>&1"
            )
            return _install_cron_line(spec.cron_marker or "", "0 4 * * 0", cmd)
        if spec.toggle_id == "quarterly_capability_cron":
            cmd = (
                f"cd {root} && source {venv} && {root}/scripts/quarterly_capability.sh "
                f">> {log_dir}/termit-quarterly-capability.log 2>&1"
            )
            return _install_cron_line(spec.cron_marker or "", "0 5 1 1,4,7,10 *", cmd)
        return False

    def _apply_runtime(self, toggle_id: str, enabled: bool) -> None:
        if toggle_id == "stage1_schedule" and self._stage1 is not None:
            self._stage1.set_enabled(enabled)
        elif toggle_id == "daily_improvement" and self._daily is not None:
            self._daily.set_enabled(enabled)
        elif toggle_id == "agent_maintenance" and self._maintenance is not None:
            self._maintenance.set_enabled(enabled)
        elif toggle_id == "agent_schedules" and self._agent_schedules is not None:
            self._agent_schedules.set_enabled(enabled)

    def _scheduler_status(self) -> dict[str, object]:
        out: dict[str, object] = {}
        if self._stage1 is not None:
            out["stage1"] = self._stage1.status()
        if self._daily is not None:
            out["daily_improvement"] = self._daily.status()
        if self._maintenance is not None:
            out["agent_maintenance"] = self._maintenance.status()
        if self._agent_schedules is not None:
            out["agent_schedules"] = self._agent_schedules.status()
        return out
