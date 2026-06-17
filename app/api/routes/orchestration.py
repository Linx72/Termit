from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    BuildFromPlanRequest,
    BuildFromPlanResponse,
    OrchestrationMetricsResponse,
    OrchestrationRunRequest,
    OrchestrationRunResponse,
)
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.services.plan_build_service import PlanBuildService
from app.services.providers.base import ProviderError
from app.state import get_multi_agent_orchestrator, get_plan_build_service

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


@router.post("/run", response_model=OrchestrationRunResponse)
async def run_orchestration(
    payload: OrchestrationRunRequest,
    orchestrator: MultiAgentOrchestrator = Depends(get_multi_agent_orchestrator),
) -> OrchestrationRunResponse:
    try:
        return await orchestrator.run(payload)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/build-from-plan", response_model=BuildFromPlanResponse)
async def build_from_plan(
    payload: BuildFromPlanRequest,
    service: PlanBuildService = Depends(get_plan_build_service),
) -> BuildFromPlanResponse:
    return service.enqueue(payload)


@router.get("/metrics", response_model=OrchestrationMetricsResponse)
async def orchestration_metrics(
    orchestrator: MultiAgentOrchestrator = Depends(get_multi_agent_orchestrator),
    plan_build: PlanBuildService = Depends(get_plan_build_service),
) -> OrchestrationMetricsResponse:
    merged = orchestrator.metrics_snapshot()
    merged.update(plan_build.metrics_snapshot())
    return OrchestrationMetricsResponse.model_validate(merged)
