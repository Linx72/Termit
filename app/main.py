from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.tools import router as tools_router
from app.core.config import get_settings
from app.web.routes import router as web_router

settings = get_settings()
app = FastAPI(
    title="Termit",
    description="Open-source AI coding orchestrator MVP",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(tasks_router)
app.include_router(tools_router)
app.include_router(web_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
