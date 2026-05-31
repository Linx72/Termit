from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import AgentEvalRunRequest, AgentEvalSuiteRunRequest
from app.services.agent_eval_service import AgentEvalService
from app.state import get_agent_eval_service

router = APIRouter(prefix="/api/agents/eval", tags=["agent-eval"])


@router.get("/scenarios")
async def list_agent_eval_scenarios(
    service: AgentEvalService = Depends(get_agent_eval_service),
) -> list[dict[str, str]]:
    return service.list_scenarios()


@router.post("/run")
async def run_agent_eval_scenario(
    payload: AgentEvalRunRequest,
    service: AgentEvalService = Depends(get_agent_eval_service),
) -> dict[str, object]:
    try:
        return await service.run_scenario(payload.scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/suite")
async def run_agent_eval_suite(
    payload: AgentEvalSuiteRunRequest,
    service: AgentEvalService = Depends(get_agent_eval_service),
) -> dict[str, object]:
    return await service.run_suite(category=payload.category)
