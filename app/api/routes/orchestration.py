from fastapi import APIRouter, Depends, HTTPException
import os

from app.domain.schemas import (
    BuildFromPlanRequest,
    BuildFromPlanResponse,
    OrchestrationConfigResponse,
    OrchestrationMetricsResponse,
    OrchestrationRunRequest,
    OrchestrationRunResponse,
)
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.services.plan_build_service import PlanBuildService
from app.services.providers.base import ProviderError
from app.state import get_multi_agent_orchestrator, get_plan_build_service, get_settings

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


@router.get("/config", response_model=OrchestrationConfigResponse)
async def orchestration_config() -> OrchestrationConfigResponse:
    settings = get_settings()
    tier = os.getenv("TERMIT_ORCH_GATE_TIER", "ci").strip().lower() or "ci"
    require_tool_loop = os.getenv("TERMIT_ORCH_REQUIRE_TOOL_LOOP", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    try:
        min_tool_loop_steps = max(0, int(os.getenv("TERMIT_ORCH_MIN_TOOL_LOOP_STEPS", "0")))
    except ValueError:
        min_tool_loop_steps = 0
    tool_loop_fallback = os.getenv("TERMIT_ORCH_TOOL_LOOP_FALLBACK", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    return OrchestrationConfigResponse(
        tool_loop_execution_enabled=settings.orchestration_tool_loop_execution_enabled,
        eval_fixture_coder_enabled=settings.orchestration_eval_fixture_coder_enabled,
        gate_tier=tier,
        require_tool_loop=require_tool_loop,
        min_tool_loop_steps=min_tool_loop_steps,
        tool_loop_fallback_enabled=tool_loop_fallback,
    )
