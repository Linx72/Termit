from fastapi import APIRouter, Depends

from app.domain.schemas import AssignmentCreateRequest, AssignmentResponse
from app.services.assignment_workspace_service import AssignmentWorkspaceService, AssignmentWorkspaceError
from app.state import get_assignment_workspace_service

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentResponse])
async def list_assignments(
    limit: int = 50,
    service: AssignmentWorkspaceService = Depends(get_assignment_workspace_service),
) -> list[AssignmentResponse]:
    return service.list_assignments(limit=limit)


@router.post("", response_model=AssignmentResponse)
async def create_assignment(
    payload: AssignmentCreateRequest,
    service: AssignmentWorkspaceService = Depends(get_assignment_workspace_service),
) -> AssignmentResponse:
    try:
        return service.create(payload)
    except AssignmentWorkspaceError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
