from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.chat_service import ChatService
from app.state import get_chat_service

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    service: ChatService = Depends(get_chat_service),
) -> HTMLResponse:
    provider_infos = service.providers_info()
    models: list[str] = []
    for info in provider_infos:
        models.extend(info.models)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"models": models},
    )
