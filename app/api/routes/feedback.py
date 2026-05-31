from fastapi import APIRouter, Depends, HTTPException, Request

from app.domain.schemas import FeedbackRequest, FeedbackResponse
from app.services.feedback_store import FeedbackStore
from app.state import get_feedback_store

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    request: Request,
    store: FeedbackStore = Depends(get_feedback_store),
) -> FeedbackResponse:
    message = payload.message.strip()
    if len(message) < 3:
        raise HTTPException(status_code=400, detail="Feedback message is too short")

    api_key = getattr(request.state, "api_key", None)
    timestamp = store.append(
        message=message,
        rating=payload.rating,
        contact=payload.contact,
        api_key=api_key,
        session_id=payload.session_id,
        task_id=payload.task_id,
        run_id=payload.run_id,
        instruction=payload.instruction,
    )
    return FeedbackResponse(status="accepted", timestamp=timestamp)
