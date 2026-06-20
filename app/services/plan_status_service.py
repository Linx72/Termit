"""Статус плана фазы 5: infra, finetune KPI, product gates, GPU/cloud blockers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from app.core.config import Settings, get_settings
from app.services.automation_control_service import AutomationControlService
from app.services.beta_cohort_service import BetaCohortService
from app.services.desktop_kpi_gate_service import DesktopKpiGateService


_CLOUD_HINTS_RU: dict[str, str] = {
    "missing_api_key": "Задайте OPENAI_COMPAT_API_KEY или OPENAI_API_KEY для cloud benchmark.",
    "ok": "Cloud benchmark готов к запуску.",
}

_RELAX_ENV_WARNING_IDS = frozenset({
    "no_gpu",
    "cloud_benchmark",
    "finetune_kpi_dev_seed",
    "beta_cohort_dev_seed",
    "dpo_dry_run",
    "comfy_sdxl_down",
})


def _relax_env_warnings_enabled() -> bool:
    return os.getenv("TERMIT_PLAN_STATUS_RELAX_ENV_WARNINGS", "").lower() in {
        "1",
        "true",
        "yes",
    }


class PlanStatusService:
    """Сбор статуса фазы 5 из сервисов Termit и infra-проб."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        kpi_gate_service: DesktopKpiGateService | None = None,
        beta_service: BetaCohortService | None = None,
        automation_service: AutomationControlService | None = None,
        project_root: Path | None = None,
        gpu_probe: Callable[[], dict[str, Any]] | None = None,
        cloud_probe: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._kpi_gate_service = kpi_gate_service
        self._beta_service = beta_service
        self._automation_service = automation_service
        self._root = project_root or Path(
            os.getenv("TERMIT_PROJECT_ROOT", Path(__file__).resolve().parents[2])
        )
        self._gpu_probe = gpu_probe or self._default_gpu_probe
        self._cloud_probe = cloud_probe or self._default_cloud_probe

    def collect(
        self,
        *,
        from_running_api: bool = False,
        external_api_ok: bool | None = None,
    ) -> dict[str, Any]:
        """Собрать отчёт plan status.

        from_running_api=True — вызов из GET /api/ops/plan-status (infra OK).
        external_api_ok — для CLI: True если /health ответил до локального сбора.
        """
        kpi_gates = self._load_kpi_gates()
        beta = self._load_beta_metrics()
        automation = self._load_automation()
        finetune_kpi = self._load_finetune_kpi()
        learning_loop = self._load_learning_loop_0423()
        beta_meta = self._load_beta_cohort_meta()
        gpu = self._gpu_probe()
        cloud = self._cloud_probe()
        comfy = self._comfy_probe()

        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        infra_ok = from_running_api or bool(external_api_ok)
        if not infra_ok:
            blockers.append(
                {
                    "id": "api_down",
                    "message": f"Termit API недоступен: {os.getenv('TERMIT_BASE_URL', 'http://127.0.0.1:8765')}",
                }
            )

        if not gpu.get("gpu_available"):
            warnings.append(
                {
                    "id": "no_gpu",
                    "message": "Нет NVIDIA GPU — DPO/HF train только dry-run; KPI +5% маловероятен.",
                }
            )

        if not cloud.get("ready"):
            reason = str(cloud.get("reason") or "")
            hint = _CLOUD_HINTS_RU.get(reason) or str(
                cloud.get("hint") or "Cloud benchmark не готов."
            )
            warnings.append({"id": "cloud_benchmark", "message": hint})

        image_provider = (self._settings.media_image_provider or "").strip().lower()
        if self._settings.media_enabled and image_provider in {"comfy", "sdxl"}:
            if not comfy.get("ready"):
                warnings.append(
                    {
                        "id": "comfy_sdxl_down",
                        "message": (
                            f"TERMIT_MEDIA_IMAGE_PROVIDER={image_provider}, "
                            "но ComfyUI недоступен — ./scripts/start_comfy_sidecar.sh"
                        ),
                    }
                )

        if finetune_kpi is not None and finetune_kpi.get("dev_only"):
            warnings.append(
                {
                    "id": "finetune_kpi_dev_seed",
                    "message": "eval_kpi_last.json — dev seed; запустите learning_loop_0423.sh для real KPI.",
                }
            )
        elif finetune_kpi is not None and not finetune_kpi.get("kpi_passed"):
            measurable = True
            if isinstance(learning_loop, dict) and learning_loop.get("kpi_measurable") is False:
                measurable = False
            if measurable:
                warnings.append(
                    {
                        "id": "finetune_kpi",
                        "message": str(
                            finetune_kpi.get("reason")
                            or "Finetune eval KPI не достигнут (цель +5%)."
                        ),
                    }
                )
        elif finetune_kpi is None:
            warnings.append(
                {
                    "id": "finetune_kpi",
                    "message": "Нет eval_kpi_last.json — запустите training_loop_full.sh.",
                }
            )

        if learning_loop is not None and not learning_loop.get("dpo_real_train"):
            warnings.append(
                {
                    "id": "dpo_dry_run",
                    "message": (
                        "Learning loop 0.4.23 без real GPU DPO "
                        "(TERMIT_REMOTE_GPU_SSH или локальный NVIDIA)."
                    ),
                }
            )

        product_gates_passed = bool(kpi_gates.get("overall_passed")) if kpi_gates else False
        if kpi_gates and not product_gates_passed:
            failed = [
                g.get("gate_id")
                for g in kpi_gates.get("gates", [])
                if isinstance(g, dict) and not g.get("passed")
            ]
            warnings.append(
                {
                    "id": "product_kpi",
                    "message": (
                        "Desktop KPI gates не пройдены "
                        f"(failed: {', '.join(map(str, failed)) or 'unknown'})."
                    ),
                }
            )

        cohort_d30 = int(beta.get("cohort_size_d30", 0) or 0) if isinstance(beta, dict) else 0
        beta_dev_seed = bool(beta_meta.get("dev_only")) if isinstance(beta_meta, dict) else False
        if beta_dev_seed:
            warnings.append(
                {
                    "id": "beta_cohort_dev_seed",
                    "message": "Beta cohort из dev seed; нужна real telemetry на staging.",
                }
            )
        elif cohort_d30 < 5:
            warnings.append(
                {
                    "id": "beta_cohort",
                    "message": (
                        f"Beta-когорта D30 слишком мала ({cohort_d30}) "
                        "для retention gate (нужно ≥5)."
                    ),
                }
            )

        relaxed_env_warnings: list[dict[str, str]] = []
        relax_enabled = _relax_env_warnings_enabled()
        if relax_enabled:
            kept: list[dict[str, str]] = []
            for item in warnings:
                if item.get("id") in _RELAX_ENV_WARNING_IDS:
                    relaxed_env_warnings.append(item)
                else:
                    kept.append(item)
            warnings = kept

        infra_ok = from_running_api or bool(external_api_ok)
        overall_ok = infra_ok and len(blockers) == 0 and len(warnings) == 0

        payload = {
            "phase": "5_production_kpi",
            "plan_code_complete": True,
            "infra_ok": infra_ok,
            "overall_ok": overall_ok,
            "relax_env_warnings_enabled": relax_enabled,
            "relaxed_env_warnings": relaxed_env_warnings,
            "automatic_mode_enabled": (
                bool(automation.get("automatic_mode_enabled")) if automation else None
            ),
            "gpu": gpu,
            "cloud_benchmark": cloud,
            "finetune_eval_kpi": finetune_kpi,
            "learning_loop_0423": learning_loop,
            "desktop_kpi_gates": kpi_gates,
            "beta_metrics": beta,
            "d30_retention": beta.get("d30_retention_rate") if isinstance(beta, dict) else None,
            "blockers": blockers,
            "warnings": warnings,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        }
        if from_running_api:
            self._persist_snapshot(payload)
        return payload

    def _persist_snapshot(self, payload: dict[str, Any]) -> None:
        """Сохранить последний plan status в data/plan_status_last.json."""
        path = self._root / "data" / "plan_status_last.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass

    def _load_kpi_gates(self) -> dict[str, Any] | None:
        if self._kpi_gate_service is not None:
            payload = self._kpi_gate_service.evaluate_gates()
            return payload if isinstance(payload, dict) else None
        return None

    def _load_beta_metrics(self) -> dict[str, Any] | None:
        if self._beta_service is not None:
            payload = self._beta_service.build_metrics()
            return payload if isinstance(payload, dict) else None
        return None

    def _load_automation(self) -> dict[str, Any] | None:
        if self._automation_service is not None:
            payload = self._automation_service.snapshot()
            return payload if isinstance(payload, dict) else None
        return None

    def _load_finetune_kpi(self) -> dict[str, Any] | None:
        path = self._root / "data" / "eval_kpi_last.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    def _load_learning_loop_0423(self) -> dict[str, Any] | None:
        path = self._root / "data" / "learning_loop_0423_last.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    def _load_beta_cohort_meta(self) -> dict[str, Any] | None:
        path = self._root / "data" / "beta_cohort_meta.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    def _comfy_probe(self) -> dict[str, Any]:
        """Проверить ComfyUI sidecar для локального SDXL."""
        from app.services.media_provider_comfy import ComfyImageProvider

        settings = self._settings
        provider = ComfyImageProvider(
            base_url=settings.media_comfy_url,
            workflow_path=settings.media_comfy_workflow,
            checkpoint=settings.media_comfy_checkpoint,
            timeout_sec=min(10.0, settings.media_comfy_timeout_sec),
        )
        ready = provider.health_check()
        return {
            "ready": ready,
            "url": settings.media_comfy_url,
            "checkpoint": settings.media_comfy_checkpoint,
        }

    @staticmethod
    def _default_gpu_probe() -> dict[str, Any]:
        root = Path(__file__).resolve().parents[2]
        python_bin = root / ".venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path(sys.executable)
        proc = subprocess.run(
            [str(python_bin), str(root / "scripts" / "gpu_probe.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
        )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"gpu_available": False, "error": proc.stderr.strip() or "gpu_probe failed"}

    @staticmethod
    def _default_cloud_probe() -> dict[str, Any]:
        root = Path(__file__).resolve().parents[2]
        python_bin = root / ".venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path(sys.executable)
        proc = subprocess.run(
            [str(python_bin), str(root / "scripts" / "cloud_benchmark_probe.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
        )
        try:
            payload = json.loads(proc.stdout)
            if isinstance(payload, dict) and payload.get("reason") == "missing_api_key":
                payload = {**payload, "hint": _CLOUD_HINTS_RU["missing_api_key"]}
            return payload
        except json.JSONDecodeError:
            return {"ready": False, "reason": "probe_failed", "hint": "Cloud benchmark probe failed."}


def build_plan_status_service() -> PlanStatusService:
    from app.state import (
        get_automation_control_service,
        get_beta_cohort_service,
        get_desktop_kpi_gate_service,
    )

    return PlanStatusService(
        kpi_gate_service=get_desktop_kpi_gate_service(),
        beta_service=get_beta_cohort_service(),
        automation_service=get_automation_control_service(),
    )
