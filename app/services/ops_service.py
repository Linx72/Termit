from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.config import Settings
from app.core.rbac import role_allows
from app.domain.schemas import (
    ExecuteCommandRequest,
    HealthzDependency,
    HealthzResponse,
    ListFilesRequest,
    OpsCheckResult,
    OpsIncidentDrillResponse,
    OpsReadinessResponse,
)
from app.services.providers.base import ProviderError
from app.services.quota_store import QuotaStore
from app.services.tooling_service import ToolingService


class OpsService:
    def __init__(
        self,
        settings: Settings,
        quota_store: QuotaStore | None = None,
        tooling: ToolingService | None = None,
    ) -> None:
        self.settings = settings
        self.quota_store = quota_store
        self.tooling = tooling or ToolingService(root_path=".")

    async def readiness(self, providers_status_cb=None, agent_metrics_cb=None) -> OpsReadinessResponse:
        checks = self._base_checks()
        if providers_status_cb is not None:
            checks.append(await self._check_providers(providers_status_cb))
        if agent_metrics_cb is not None:
            checks.append(self._check_agent_verify_quality(agent_metrics_cb))
        return self._build_response(checks, OpsReadinessResponse)

    async def healthz(
        self,
        *,
        version: str,
        providers_status_cb=None,
        agent_workers_cb=None,
        maintenance_status_cb=None,
        local_runtime_status_cb=None,
    ) -> HealthzResponse:
        import time

        dependencies: list[HealthzDependency] = []
        for check in self._healthz_storage_checks():
            started = time.perf_counter()
            dependency = self._dependency_from_check(check, started)
            dependencies.append(dependency)

        if providers_status_cb is not None:
            started = time.perf_counter()
            check = await self._check_providers(providers_status_cb)
            dependencies.append(self._dependency_from_check(check, started))

        if agent_workers_cb is not None:
            started = time.perf_counter()
            dependencies.append(self._check_agent_workers(agent_workers_cb, started))

        if maintenance_status_cb is not None:
            started = time.perf_counter()
            dependencies.append(self._check_maintenance_scheduler(maintenance_status_cb, started))

        if local_runtime_status_cb is not None:
            started = time.perf_counter()
            dependencies.append(await self._check_local_runtime(local_runtime_status_cb, started))

        status = self._aggregate_health_status(dependencies)
        return HealthzResponse(status=status, version=version, dependencies=dependencies)

    async def incident_drill(self, providers_status_cb=None) -> OpsIncidentDrillResponse:
        checks = self._base_checks()
        checks.extend(self._drill_only_checks())
        if providers_status_cb is not None:
            checks.append(await self._check_providers(providers_status_cb))
        summary = self._build_response(checks, OpsReadinessResponse)
        actions = self._recommended_actions(summary.checks)
        return OpsIncidentDrillResponse(
            run_id=f"drill_{uuid4().hex[:12]}",
            status=summary.status,
            passed=summary.passed,
            failed=summary.failed,
            checks=summary.checks,
            recommended_actions=actions,
        )

    def _healthz_storage_checks(self) -> list[OpsCheckResult]:
        return [
            self._check_path_writable(self.settings.memory_sqlite_path, "memory_sqlite"),
            self._check_path_writable(self.settings.task_sqlite_path, "task_sqlite"),
            self._check_path_writable(self.settings.agent_run_sqlite_path, "agent_run_sqlite"),
            self._check_path_writable(self.settings.quota_sqlite_path, "quota_sqlite"),
            self._check_agent_registry_path(),
        ]

    def _check_agent_registry_path(self) -> OpsCheckResult:
        path = Path(self.settings.agent_registry_file_path).resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return OpsCheckResult(
                name="agent_registry",
                passed=True,
                severity="info",
                detail=f"Agent registry path ready ({path.parent})",
            )
        except OSError as exc:
            return OpsCheckResult(
                name="agent_registry",
                passed=False,
                severity="critical",
                detail=f"Agent registry path unavailable: {exc}",
            )

    @staticmethod
    def _dependency_from_check(check: OpsCheckResult, started: float) -> HealthzDependency:
        import time

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if not check.passed:
            status = "unhealthy" if check.severity == "critical" else "degraded"
        else:
            status = "ok"
        return HealthzDependency(
            name=check.name,
            status=status,
            detail=check.detail,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _check_agent_workers(agent_workers_cb, started: float) -> HealthzDependency:
        import time

        metrics = agent_workers_cb()
        worker_count = int(metrics.get("worker_count", 0))
        alive_workers = int(metrics.get("alive_workers", 0))
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if worker_count <= 0:
            return HealthzDependency(
                name="agent_workers",
                status="unhealthy",
                detail="Agent worker pool is not configured.",
                latency_ms=latency_ms,
            )
        if alive_workers <= 0:
            return HealthzDependency(
                name="agent_workers",
                status="unhealthy",
                detail=f"No agent workers alive (configured={worker_count}).",
                latency_ms=latency_ms,
            )
        if alive_workers < worker_count:
            return HealthzDependency(
                name="agent_workers",
                status="degraded",
                detail=f"Partial worker availability ({alive_workers}/{worker_count} alive).",
                latency_ms=latency_ms,
            )
        return HealthzDependency(
            name="agent_workers",
            status="ok",
            detail=f"All agent workers alive ({alive_workers}/{worker_count}).",
            latency_ms=latency_ms,
        )

    @staticmethod
    def _check_maintenance_scheduler(maintenance_status_cb, started: float) -> HealthzDependency:
        import time

        status_payload = maintenance_status_cb()
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        enabled = bool(status_payload.get("enabled"))
        if not enabled:
            return HealthzDependency(
                name="agent_maintenance",
                status="ok",
                detail="Agent maintenance scheduler disabled by config.",
                latency_ms=latency_ms,
            )
        thread_alive = bool(status_payload.get("thread_alive"))
        cleanup_errors = int(status_payload.get("cleanup_errors_total", 0))
        snapshot_errors = int(status_payload.get("snapshot_errors_total", 0))
        if not thread_alive:
            return HealthzDependency(
                name="agent_maintenance",
                status="degraded",
                detail="Maintenance scheduler enabled but thread is not alive.",
                latency_ms=latency_ms,
            )
        if cleanup_errors > 0 or snapshot_errors > 0:
            return HealthzDependency(
                name="agent_maintenance",
                status="degraded",
                detail=(
                    f"Maintenance scheduler running with errors "
                    f"(cleanup={cleanup_errors}, snapshot={snapshot_errors})."
                ),
                latency_ms=latency_ms,
            )
        return HealthzDependency(
            name="agent_maintenance",
            status="ok",
            detail="Maintenance scheduler running.",
            latency_ms=latency_ms,
        )

    @staticmethod
    async def _check_local_runtime(local_runtime_status_cb, started: float) -> HealthzDependency:
        import time

        try:
            runtime_status = await local_runtime_status_cb()
        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return HealthzDependency(
                name="local_runtime",
                status="degraded",
                detail=f"Local runtime probe failed: {exc}",
                latency_ms=latency_ms,
            )

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        providers = getattr(runtime_status, "providers", []) or []
        healthy = [item for item in providers if getattr(item, "ok", False)]
        if not providers:
            return HealthzDependency(
                name="local_runtime",
                status="degraded",
                detail="No local runtime providers configured.",
                latency_ms=latency_ms,
            )
        if not healthy:
            return HealthzDependency(
                name="local_runtime",
                status="degraded",
                detail="Local runtime providers are unavailable.",
                latency_ms=latency_ms,
            )
        names = ", ".join(item.provider for item in healthy)
        return HealthzDependency(
            name="local_runtime",
            status="ok",
            detail=f"Healthy local runtime providers: {names}",
            latency_ms=latency_ms,
        )

    @staticmethod
    def _aggregate_health_status(dependencies: list[HealthzDependency]) -> str:
        if any(item.status == "unhealthy" for item in dependencies):
            return "unhealthy"
        if any(item.status == "degraded" for item in dependencies):
            return "degraded"
        return "ok"

    def _base_checks(self) -> list[OpsCheckResult]:
        return [
            self._check_auth_configuration(),
            self._check_path_writable(self.settings.memory_sqlite_path, "memory_sqlite"),
            self._check_path_writable(self.settings.task_sqlite_path, "task_sqlite"),
            self._check_path_writable(self.settings.quota_sqlite_path, "quota_sqlite"),
            self._check_eval_scenarios(),
            self._check_rbac_boundaries(),
            self._check_tool_safety(),
            self._check_feedback_path(),
            self._check_retrieval_root(),
        ]

    def _drill_only_checks(self) -> list[OpsCheckResult]:
        checks = [
            self._check_circuit_breaker_config(),
            self._check_quota_store_roundtrip(),
            self._check_auth_roles_present(),
        ]
        return checks

    def _check_auth_configuration(self) -> OpsCheckResult:
        if not self.settings.auth_enabled:
            return OpsCheckResult(
                name="auth_configuration",
                passed=True,
                severity="info",
                detail="Auth disabled (acceptable for local beta).",
            )
        if not self.settings.api_keys:
            return OpsCheckResult(
                name="auth_configuration",
                passed=False,
                severity="critical",
                detail="Auth enabled but TERMIT_API_KEYS is empty.",
            )
        invalid = [
            key
            for key, cfg in self.settings.api_keys.items()
            if cfg.daily_quota <= 0 or cfg.role not in {"viewer", "operator", "admin"}
        ]
        if invalid:
            return OpsCheckResult(
                name="auth_configuration",
                passed=False,
                severity="critical",
                detail=f"Invalid API key config for: {', '.join(invalid[:3])}",
            )
        return OpsCheckResult(
            name="auth_configuration",
            passed=True,
            severity="info",
            detail=f"Auth enabled with {len(self.settings.api_keys)} configured keys.",
        )

    def _check_path_writable(self, path_value: str, name: str) -> OpsCheckResult:
        path = Path(path_value).resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            probe = path.parent / f".{name}_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return OpsCheckResult(
                name=f"{name}_writable",
                passed=True,
                severity="info",
                detail=f"Writable path verified for {path}",
            )
        except OSError as exc:
            return OpsCheckResult(
                name=f"{name}_writable",
                passed=False,
                severity="critical",
                detail=f"Path not writable ({path}): {exc}",
            )

    def _check_eval_scenarios(self) -> OpsCheckResult:
        path = Path(self.settings.eval_scenarios_path)
        if not path.exists():
            return OpsCheckResult(
                name="eval_scenarios",
                passed=False,
                severity="warning",
                detail=f"Eval scenarios file missing: {path}",
            )
        return OpsCheckResult(
            name="eval_scenarios",
            passed=True,
            severity="info",
            detail=f"Eval scenarios present at {path}",
        )

    def _check_rbac_boundaries(self) -> OpsCheckResult:
        viewer_execute = role_allows("viewer", "POST", "/api/tools/execute_command")
        operator_execute = role_allows("operator", "POST", "/api/tools/execute_command")
        viewer_delete = role_allows("viewer", "DELETE", "/api/sessions/abc")
        if viewer_execute or not operator_execute or viewer_delete:
            return OpsCheckResult(
                name="rbac_boundaries",
                passed=False,
                severity="critical",
                detail="RBAC policy mismatch for viewer/operator boundaries.",
            )
        return OpsCheckResult(
            name="rbac_boundaries",
            passed=True,
            severity="info",
            detail="Viewer/operator/admin boundaries validated.",
        )

    def _check_tool_safety(self) -> OpsCheckResult:
        result = self.tooling.execute_command(
            ExecuteCommandRequest(command="rm -rf /", path=".", dry_run=False, confirmed=True)
        )
        blocked = not result.executed and "blocked" in (result.stderr or "").lower()
        if not blocked:
            return OpsCheckResult(
                name="tool_safety",
                passed=False,
                severity="critical",
                detail="Destructive command was not blocked by policy.",
            )
        return OpsCheckResult(
            name="tool_safety",
            passed=True,
            severity="info",
            detail="Destructive command blocked as expected.",
        )

    def _check_feedback_path(self) -> OpsCheckResult:
        path = Path(self.settings.feedback_file_path).resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return OpsCheckResult(
                name="feedback_path",
                passed=True,
                severity="info",
                detail=f"Feedback path ready ({path.parent})",
            )
        except OSError as exc:
            return OpsCheckResult(
                name="feedback_path",
                passed=False,
                severity="warning",
                detail=f"Feedback path unavailable: {exc}",
            )

    def _check_retrieval_root(self) -> OpsCheckResult:
        root = Path(self.settings.retrieval_root_path).resolve()
        if not root.exists():
            return OpsCheckResult(
                name="retrieval_root",
                passed=False,
                severity="warning",
                detail=f"Retrieval root missing: {root}",
            )
        listing = self.tooling.list_files(ListFilesRequest(path=".", pattern="*.py"))
        passed = len(listing.files) > 0
        return OpsCheckResult(
            name="retrieval_root",
            passed=passed,
            severity="info" if passed else "warning",
            detail=f"Retrieval root contains {len(listing.files)} Python files.",
        )

    def _check_circuit_breaker_config(self) -> OpsCheckResult:
        ok = (
            self.settings.circuit_failure_threshold >= 1
            and self.settings.circuit_cooldown_seconds >= 5
        )
        return OpsCheckResult(
            name="circuit_breaker_config",
            passed=ok,
            severity="warning" if ok else "critical",
            detail=(
                f"threshold={self.settings.circuit_failure_threshold}, "
                f"cooldown={self.settings.circuit_cooldown_seconds}s"
            ),
        )

    def _check_quota_store_roundtrip(self) -> OpsCheckResult:
        if self.quota_store is None:
            if not self.settings.auth_enabled:
                return OpsCheckResult(
                    name="quota_store_roundtrip",
                    passed=True,
                    severity="info",
                    detail="Quota store not required while auth is disabled.",
                )
            return OpsCheckResult(
                name="quota_store_roundtrip",
                passed=False,
                severity="critical",
                detail="Auth enabled but quota store is not initialized.",
            )
        probe_key = "__drill_probe__"
        allowed, used, limit = self.quota_store.consume(probe_key, daily_limit=10_000)
        self.quota_store.reset_usage(probe_key)
        if not allowed:
            return OpsCheckResult(
                name="quota_store_roundtrip",
                passed=False,
                severity="critical",
                detail="Quota consume probe failed unexpectedly.",
            )
        return OpsCheckResult(
            name="quota_store_roundtrip",
            passed=True,
            severity="info",
            detail=f"Quota roundtrip ok (probe used={used}, limit={limit}).",
        )

    def _check_auth_roles_present(self) -> OpsCheckResult:
        if not self.settings.auth_enabled:
            return OpsCheckResult(
                name="auth_roles_present",
                passed=True,
                severity="info",
                detail="Skipped (auth disabled).",
            )
        roles = {cfg.role for cfg in self.settings.api_keys.values()}
        has_operator = "operator" in roles or "admin" in roles
        has_viewer = "viewer" in roles or "admin" in roles
        passed = has_operator and has_viewer
        return OpsCheckResult(
            name="auth_roles_present",
            passed=passed,
            severity="warning" if passed else "critical",
            detail=f"Configured roles: {', '.join(sorted(roles))}",
        )

    async def _check_providers(self, providers_status_cb) -> OpsCheckResult:
        try:
            statuses = await providers_status_cb()
        except ProviderError as exc:
            return OpsCheckResult(
                name="providers_status",
                passed=False,
                severity="warning",
                detail=f"Provider status check failed: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            return OpsCheckResult(
                name="providers_status",
                passed=False,
                severity="warning",
                detail=f"Provider status check error: {exc}",
            )

        if not statuses:
            return OpsCheckResult(
                name="providers_status",
                passed=False,
                severity="warning",
                detail="No providers configured.",
            )
        healthy = [item for item in statuses if item.ok]
        if not healthy:
            return OpsCheckResult(
                name="providers_status",
                passed=False,
                severity="warning",
                detail="All providers are currently unavailable.",
            )
        names = ", ".join(item.provider for item in healthy)
        return OpsCheckResult(
            name="providers_status",
            passed=True,
            severity="info",
            detail=f"Healthy providers: {names}",
        )

    def _check_agent_verify_quality(self, agent_metrics_cb) -> OpsCheckResult:
        try:
            metrics = agent_metrics_cb()
        except Exception as exc:  # noqa: BLE001
            return OpsCheckResult(
                name="agent_verify_quality",
                passed=False,
                severity="warning",
                detail=f"Agent verify metrics probe failed: {exc}",
            )
        if not isinstance(metrics, dict):
            return OpsCheckResult(
                name="agent_verify_quality",
                passed=False,
                severity="warning",
                detail="Agent verify metrics payload is invalid.",
            )
        verify_passes = int(metrics.get("tool_loop_verify_passes", 0))
        verify_failures = int(metrics.get("tool_loop_verify_failures", 0))
        total_verify = verify_passes + verify_failures
        if total_verify <= 0:
            return OpsCheckResult(
                name="agent_verify_quality",
                passed=True,
                severity="info",
                detail="No verify observations yet.",
            )
        verify_pass_rate = float(metrics.get("tool_loop_verify_pass_rate", 0.0))
        threshold = float(self.settings.agent_alert_min_verify_pass_rate)
        if verify_pass_rate < threshold:
            return OpsCheckResult(
                name="agent_verify_quality",
                passed=False,
                severity="warning",
                detail=(
                    f"Verify pass rate {verify_pass_rate:.2%} below threshold {threshold:.2%} "
                    f"(passes={verify_passes}, failures={verify_failures})."
                ),
            )
        return OpsCheckResult(
            name="agent_verify_quality",
            passed=True,
            severity="info",
            detail=(
                f"Verify pass rate healthy at {verify_pass_rate:.2%} "
                f"(threshold {threshold:.2%}, total={total_verify})."
            ),
        )

    @staticmethod
    def _build_response(checks: list[OpsCheckResult], response_cls):
        passed = sum(1 for item in checks if item.passed)
        failed = len(checks) - passed
        critical_failed = any(
            (not item.passed) and item.severity == "critical" for item in checks
        )
        if critical_failed:
            status = "unhealthy"
        elif failed > 0:
            status = "degraded"
        else:
            status = "ready"
        return response_cls(
            status=status,
            passed=passed,
            failed=failed,
            checks=checks,
        )

    @staticmethod
    def _recommended_actions(checks: list[OpsCheckResult]) -> list[str]:
        actions: list[str] = []
        for check in checks:
            if check.passed:
                continue
            if check.name == "auth_configuration":
                actions.append("Set TERMIT_API_KEYS=key:quota:role:team and restart service.")
            elif check.name == "providers_status":
                actions.append("Verify Ollama/OpenAI-compatible endpoints and fallback models.")
            elif check.name == "quota_store_roundtrip":
                actions.append("Ensure TERMIT_QUOTA_SQLITE_PATH is writable and auth middleware is active.")
            elif check.name == "tool_safety":
                actions.append("Stop traffic and inspect tooling policy before continuing beta.")
            else:
                actions.append(f"Investigate failed check '{check.name}': {check.detail}")
        if not actions:
            actions.append("All drill checks passed. Capture metrics snapshot for weekly KPI review.")
        return actions

    @staticmethod
    def mask_api_key(api_key: str) -> str:
        if len(api_key) <= 4:
            return "****"
        return f"{'*' * (len(api_key) - 4)}{api_key[-4:]}"
