import asyncio
import logging
import os
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.structured_logging import configure_logging

from app.api.routes.assignments import router as assignments_router
from app.api.routes.automation import router as automation_router
from app.api.routes.agents import router as agents_router
from app.api.routes.agent_eval import router as agent_eval_router
from app.api.routes.chat import router as chat_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.tools import router as tools_router
from app.api.routes.eval import router as eval_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.local_runtime import router as local_runtime_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.media import router as media_router
from app.api.routes.ops import router as ops_router
from app.api.routes.desktop import router as desktop_router
from app.api.routes.cross_platform import router as cross_platform_router
from app.api.routes.orchestration import router as orchestration_router
from app.api.routes.platform import router as platform_router
from app.api.routes.projects import router as projects_router
from app.api.routes.routing import router as routing_router
from app.api.routes.finetune import router as finetune_router
from app.api.routes.teams import router as teams_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.plugin_tools import router as plugin_tools_router
from app.api.routes.session_search import router as session_search_router
from app.api.routes.health import router as health_router
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.request_trace import RequestTraceMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.api.routes.usage import router as usage_router
from app.core.config import get_settings
from app.middleware.auth_quota import AuthQuotaMiddleware
from app.services.quota_store import QuotaStore
from app.domain.schemas import HealthzResponse
from app.state import (
    get_agent_maintenance_scheduler_service,
    get_agent_service,
    get_chat_service,
    get_local_runtime_service,
    get_ops_service,
    get_quota_store,
    get_stage1_scheduler_service,
    get_daily_improvement_scheduler_service,
)
from app.web.routes import router as web_router

settings = get_settings()
configure_logging(json_logs=settings.log_json, level=settings.log_level)
_version_file = Path(__file__).resolve().parent.parent / "VERSION"
_app_version = (
    _version_file.read_text(encoding="utf-8").strip()
    if _version_file.exists()
    else "0.1.0"
)


_logger = logging.getLogger("termit.startup")


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    agent_service = get_agent_service()
    stage1_scheduler = get_stage1_scheduler_service()
    daily_improvement_scheduler = get_daily_improvement_scheduler_service()
    maintenance_scheduler = get_agent_maintenance_scheduler_service()
    from app.state import get_agent_schedule_service

    agent_schedule_service = get_agent_schedule_service()
    local_runtime = get_local_runtime_service()
    if settings.auto_start_ollama:
        script = Path(__file__).resolve().parent.parent / "scripts" / "start_ollama_local.sh"
        if script.exists():
            import subprocess

            subprocess.run(["/bin/bash", str(script)], check=False, capture_output=True)
    skip_ollama_check = os.getenv("TERMIT_SKIP_OLLAMA_CHECK", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if skip_ollama_check:
        _logger.info("Ollama model check skipped (TERMIT_SKIP_OLLAMA_CHECK=1).")
    else:
        try:
            _required, missing = await local_runtime.check_required_models()
            if missing:
                pull_hint = " && ollama pull ".join(missing)
                _logger.error(
                    "Missing Ollama models: %s. Install with: ollama pull %s",
                    ", ".join(missing),
                    pull_hint,
                )
            else:
                _logger.info("Ollama model check passed (%d required).", len(_required))
            if settings.ollama_warm_on_startup:
                warm = await local_runtime.warm_ollama_models(max_models=settings.ollama_warm_max_models)
                _logger.info(
                    "Ollama warm on startup: warmed=%s total=%s",
                    warm.get("warmed"),
                    warm.get("total"),
                )
        except Exception as exc:  # noqa: BLE001 — startup must not crash on probe failure
            _logger.warning("Ollama model validation skipped: %s", exc)
    agent_service.start()
    stage1_scheduler.start()
    daily_improvement_scheduler.start()
    maintenance_scheduler.start()
    yield
    maintenance_scheduler.stop()
    agent_schedule_service.stop()
    daily_improvement_scheduler.stop()
    stage1_scheduler.stop()
    await asyncio.to_thread(
        agent_service.stop,
        grace_seconds=float(settings.agent_shutdown_grace_seconds),
    )


app = FastAPI(
    title="Termit",
    description="Open-source AI coding orchestrator MVP",
    version=_app_version,
    lifespan=_app_lifespan,
)

app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
# Per-endpoint rate limiting (before CORS/quota to protect unauthenticated endpoints)
if settings.rate_limit_endpoints:
    app.add_middleware(RateLimitMiddleware, endpoint_limits=settings.rate_limit_endpoints)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

quota_store = None
if settings.auth_enabled and settings.api_keys:
    quota_store = get_quota_store()

app.add_middleware(AuthQuotaMiddleware, settings=settings, quota_store=quota_store)
app.add_middleware(RequestTraceMiddleware)

app.include_router(chat_router)
app.include_router(usage_router)
app.include_router(metrics_router)
app.include_router(feedback_router)
app.include_router(eval_router)
app.include_router(retrieval_router)
app.include_router(plugin_tools_router)
app.include_router(session_search_router)
app.include_router(ops_router)
app.include_router(automation_router)
app.include_router(assignments_router)
app.include_router(media_router)
app.include_router(tasks_router)
app.include_router(tools_router)
app.include_router(local_runtime_router)
app.include_router(agents_router)
app.include_router(agent_eval_router)
app.include_router(teams_router)
app.include_router(orchestration_router)
app.include_router(cross_platform_router)
app.include_router(desktop_router)
app.include_router(projects_router)
app.include_router(platform_router)
app.include_router(routing_router)
app.include_router(finetune_router)
app.include_router(web_router)
app.include_router(health_router)

_static_dir = Path(__file__).resolve().parent / "web" / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    ops = get_ops_service()
    chat = get_chat_service()
    agent_service = get_agent_service()
    maintenance = get_agent_maintenance_scheduler_service()
    local_runtime = get_local_runtime_service()
    return await ops.healthz(
        version=_app_version,
        providers_status_cb=chat.providers_status,
        agent_workers_cb=agent_service.queue_metrics,
        maintenance_status_cb=maintenance.status,
        local_runtime_status_cb=local_runtime.status,
    )
