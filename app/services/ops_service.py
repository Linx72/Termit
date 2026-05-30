from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.config import Settings
from app.core.rbac import role_allows
from app.domain.schemas import (
    ExecuteCommandRequest,
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

    async def readiness(self, providers_status_cb=None) -> OpsReadinessResponse:
        checks = self._base_checks()
        if providers_status_cb is not None:
            checks.append(await self._check_providers(providers_status_cb))
        return self._build_response(checks, OpsReadinessResponse)

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
