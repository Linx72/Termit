from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import WebAutomationRequest, WebAutomationResponse
from app.services.browser_workflow_service import BrowserWorkflowService, WebWorkflowError
from app.state import get_browser_workflow_service

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.post("/web", response_model=WebAutomationResponse)
async def run_web_automation(
    payload: WebAutomationRequest,
    service: BrowserWorkflowService = Depends(get_browser_workflow_service),
) -> WebAutomationResponse:
    try:
        return service.run(payload)
    except WebWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
