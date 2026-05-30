from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.automation import router as automation_router
from app.api.routes.agents import router as agents_router
from app.api.routes.chat import router as chat_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.tools import router as tools_router
from app.api.routes.eval import router as eval_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.local_runtime import router as local_runtime_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.ops import router as ops_router
from app.api.routes.orchestration import router as orchestration_router
from app.api.routes.routing import router as routing_router
from app.api.routes.finetune import router as finetune_router
from app.api.routes.teams import router as teams_router
from app.api.routes.retrieval import router as retrieval_router
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.api.routes.usage import router as usage_router
from app.core.config import get_settings
from app.middleware.auth_quota import AuthQuotaMiddleware
from app.services.quota_store import QuotaStore
from app.state import get_quota_store
from app.web.routes import router as web_router

settings = get_settings()
_version_file = Path(__file__).resolve().parent.parent / "VERSION"
_app_version = (
    _version_file.read_text(encoding="utf-8").strip()
    if _version_file.exists()
    else "0.1.0"
)
app = FastAPI(
    title="Termit",
    description="Open-source AI coding orchestrator MVP",
    version=_app_version,
)

app.add_middleware(SecurityHeadersMiddleware)
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

app.include_router(chat_router)
app.include_router(usage_router)
app.include_router(metrics_router)
app.include_router(feedback_router)
app.include_router(eval_router)
app.include_router(retrieval_router)
app.include_router(ops_router)
app.include_router(automation_router)
app.include_router(tasks_router)
app.include_router(tools_router)
app.include_router(local_runtime_router)
app.include_router(agents_router)
app.include_router(teams_router)
app.include_router(orchestration_router)
app.include_router(routing_router)
app.include_router(finetune_router)
app.include_router(web_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
