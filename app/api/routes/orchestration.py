from fastapi import APIRouter, Depends

from app.domain.schemas import (
    OrchestrationMetricsResponse,
    OrchestrationRunRequest,
    OrchestrationRunResponse,
)
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.state import get_multi_agent_orchestrator

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


@router.post("/run", response_model=OrchestrationRunResponse)
async def run_orchestration(
    payload: OrchestrationRunRequest,
    orchestrator: MultiAgentOrchestrator = Depends(get_multi_agent_orchestrator),
) -> OrchestrationRunResponse:
    return await orchestrator.run(payload)


@router.get("/metrics", response_model=OrchestrationMetricsResponse)
async def orchestration_metrics(
    orchestrator: MultiAgentOrchestrator = Depends(get_multi_agent_orchestrator),
) -> OrchestrationMetricsResponse:
    return OrchestrationMetricsResponse.model_validate(orchestrator.metrics_snapshot())
