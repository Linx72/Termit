from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    AgentPolicyPresetResponse,
    DesktopHeavyJobListResponse,
    DesktopHeavyJobRequest,
    DesktopHeavyJobResponse,
    DesktopJourneyResponse,
    DesktopKpiGateItem,
    DesktopKpiGateResponse,
    DesktopNorthStarResponse,
    DesktopShareRunRequest,
    DesktopShareRunResponse,
    DesktopSharedRunListResponse,
    DesktopWorkflowEventRequest,
    DesktopWorkflowEventResponse,
    OnboardingMetricsResponse,
    OnboardingVariantMetrics,
)
from app.services.agent_policy_preset_service import AgentPolicyPresetService
from app.services.desktop_accelerator_service import DesktopAcceleratorService
from app.services.desktop_kpi_gate_service import DesktopKpiGateService
from app.services.desktop_workflow_telemetry_service import DesktopWorkflowTelemetryService
from app.services.onboarding_experiment_service import OnboardingExperimentService
from app.state import (
    get_agent_policy_preset_service,
    get_desktop_accelerator_service,
    get_desktop_kpi_gate_service,
    get_desktop_workflow_telemetry_service,
    get_onboarding_experiment_service,
)

router = APIRouter(prefix="/api/desktop", tags=["desktop"])


@router.get("/journeys", response_model=DesktopNorthStarResponse)
async def list_journeys(
    service: DesktopKpiGateService = Depends(get_desktop_kpi_gate_service),
) -> DesktopNorthStarResponse:
    payload = service.journeys_payload()
    journeys = [
        DesktopJourneyResponse(**item)
        for item in payload.get("journeys", [])
        if isinstance(item, dict)
    ]
    targets = payload.get("kpi_targets", {})
    return DesktopNorthStarResponse(
        journeys=journeys,
        kpi_targets={str(key): float(value) for key, value in targets.items()},
    )


@router.post("/workflow-events", response_model=DesktopWorkflowEventResponse)
async def record_workflow_event(
    payload: DesktopWorkflowEventRequest,
    service: DesktopWorkflowTelemetryService = Depends(get_desktop_workflow_telemetry_service),
) -> DesktopWorkflowEventResponse:
    row = service.record(
        event_type=payload.event_type,
        journey_id=payload.journey_id,
        execution_mode=payload.execution_mode,
        duration_ms=payload.duration_ms,
        ok=payload.ok,
        detail=payload.detail,
        metadata=payload.metadata,
    )
    return DesktopWorkflowEventResponse(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        timestamp=str(row["timestamp"]),
    )


@router.get("/onboarding-metrics", response_model=OnboardingMetricsResponse)
async def onboarding_metrics(
    telemetry: DesktopWorkflowTelemetryService = Depends(get_desktop_workflow_telemetry_service),
    experiment: OnboardingExperimentService = Depends(get_onboarding_experiment_service),
) -> OnboardingMetricsResponse:
    summary = experiment.summarize(telemetry.list_events())
    variants = [
        OnboardingVariantMetrics(**item)
        for item in summary.get("variants", [])
        if isinstance(item, dict)
    ]
    return OnboardingMetricsResponse(
        total_assigned=int(summary.get("total_assigned", 0)),
        total_completed=int(summary.get("total_completed", 0)),
        overall_conversion_rate=summary.get("overall_conversion_rate"),
        variants=variants,
        unknown_assigned=int(summary.get("unknown_assigned", 0)),
        unknown_completed=int(summary.get("unknown_completed", 0)),
    )


@router.get("/kpi-gates", response_model=DesktopKpiGateResponse)
async def kpi_gates(
    service: DesktopKpiGateService = Depends(get_desktop_kpi_gate_service),
) -> DesktopKpiGateResponse:
    payload = service.evaluate_gates()
    journeys = [
        DesktopJourneyResponse(**item)
        for item in payload.get("journeys", [])
        if isinstance(item, dict)
    ]
    gates = [DesktopKpiGateItem(**item) for item in payload.get("gates", []) if isinstance(item, dict)]
    targets = payload.get("targets", {})
    return DesktopKpiGateResponse(
        overall_passed=bool(payload.get("overall_passed")),
        passed_count=int(payload.get("passed_count", 0)),
        total_gates=int(payload.get("total_gates", 0)),
        gates=gates,
        targets={str(key): float(value) for key, value in targets.items()},
        journeys=journeys,
    )


@router.get("/policy-presets", response_model=list[AgentPolicyPresetResponse])
async def list_policy_presets(
    service: AgentPolicyPresetService = Depends(get_agent_policy_preset_service),
) -> list[AgentPolicyPresetResponse]:
    return [
        AgentPolicyPresetResponse(**service.preset_to_dict(preset))
        for preset in service.list_presets()
    ]


@router.get("/shared-runs", response_model=DesktopSharedRunListResponse)
async def list_shared_runs(
    limit: int = 30,
    team: str | None = None,
    service: DesktopAcceleratorService = Depends(get_desktop_accelerator_service),
) -> DesktopSharedRunListResponse:
    rows = service.list_shared_runs(limit=limit, team=team)
    shared = [DesktopShareRunResponse(**row) for row in rows]
    return DesktopSharedRunListResponse(shared_runs=shared, total=len(shared))


@router.post("/shared-runs", response_model=DesktopShareRunResponse)
async def share_run(
    payload: DesktopShareRunRequest,
    service: DesktopAcceleratorService = Depends(get_desktop_accelerator_service),
) -> DesktopShareRunResponse:
    record = service.share_run(
        run_id=payload.run_id,
        team=payload.team,
        note=payload.note,
        shared_by=payload.shared_by,
    )
    return DesktopShareRunResponse(**record)


@router.get("/heavy-jobs", response_model=DesktopHeavyJobListResponse)
async def list_heavy_jobs(
    limit: int = 20,
    service: DesktopAcceleratorService = Depends(get_desktop_accelerator_service),
) -> DesktopHeavyJobListResponse:
    rows = service.list_heavy_jobs(limit=limit)
    jobs = [DesktopHeavyJobResponse(**row) for row in rows]
    return DesktopHeavyJobListResponse(jobs=jobs, total=len(jobs))


@router.post("/heavy-jobs", response_model=DesktopHeavyJobResponse)
async def enqueue_heavy_job(
    payload: DesktopHeavyJobRequest,
    service: DesktopAcceleratorService = Depends(get_desktop_accelerator_service),
) -> DesktopHeavyJobResponse:
    try:
        record = service.enqueue_heavy_job(
            job_type=payload.job_type,
            payload=payload.payload,
            requested_by=payload.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DesktopHeavyJobResponse(**record)


@router.get("/heavy-jobs/{job_id}", response_model=DesktopHeavyJobResponse)
async def get_heavy_job(
    job_id: str,
    service: DesktopAcceleratorService = Depends(get_desktop_accelerator_service),
) -> DesktopHeavyJobResponse:
    record = service.get_heavy_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Heavy job not found: {job_id}")
    return DesktopHeavyJobResponse(**record)
