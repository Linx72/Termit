import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    EvalBenchmarkRequest,
    EvalBenchmarkResponse,
    EvalCapabilityBaselineRefreshResponse,
    EvalCapabilityRegressionResponse,
    EvalCapabilityReviewResponse,
    EvalDashboardResponse,
    EvalReportSummaryResponse,
    EvalRunRequest,
    EvalRunResponse,
    EvalScenarioResponse,
    EvalSuiteRunRequest,
    EvalSuiteRunResponse,
    RoutingBenchmarkSyncRequest,
    RoutingBenchmarkSyncResponse,
)
from app.core.frontier_models import resolve_benchmark_reference_model
from app.services.eval_benchmark_service import EvalBenchmarkService
from app.services.eval_ci_gate import (
    DEEP_GATE,
    FAST_GATE,
    MODEL_BOUND_CI_GATE,
    MODEL_BOUND_RELEASE_GATE,
    RELEASE_GATE,
    evaluate_tier_gate,
)
from app.services.eval_service import EvalService
from app.services.routing_benchmark_sync_service import RoutingBenchmarkSyncService
from app.state import get_eval_service, get_routing_policy_service, get_settings

router = APIRouter(prefix="/api/eval", tags=["eval"])


def _scenario_category_map(service: EvalService) -> dict[str, str]:
    return {item.id: item.category for item in service.list_scenarios()}


def _sync_routing_from_benchmark(
    *,
    report: dict[str, object],
    service: EvalService,
    blend_alpha: float,
    persist: bool,
    dry_run: bool,
) -> dict[str, object]:
    sync = RoutingBenchmarkSyncService(
        get_routing_policy_service(),
        report_file_path=get_settings().eval_report_file_path,
    )
    return sync.sync_from_report(
        report,
        category_by_scenario_id=_scenario_category_map(service),
        blend_alpha=blend_alpha,
        persist=persist,
        dry_run=dry_run,
    )


def _to_run_response(result: dict[str, object]) -> EvalRunResponse:
    return EvalRunResponse(
        scenario_id=str(result["scenario_id"]),
        category=str(result["category"]),
        title=str(result["title"]),
        status=str(result["status"]),
        message=str(result["message"]),
        prompt=str(result["prompt"]),
        task_success=int(result.get("task_success", 0)),
        safety_compliance=int(result.get("safety_compliance", 1)),
        automation_level=str(result.get("automation_level", "manual assisted")),
        duration_ms=int(result.get("duration_ms", 0)),
        failure_class=str(result["failure_class"]) if result.get("failure_class") else None,
        execution_ref=str(result["execution_ref"]) if result.get("execution_ref") else None,
        model=str(result["model"]) if result.get("model") else None,
    )


@router.get("/scenarios", response_model=list[EvalScenarioResponse])
async def list_scenarios(
    service: EvalService = Depends(get_eval_service),
) -> list[EvalScenarioResponse]:
    return [
        EvalScenarioResponse(
            id=item.id,
            category=item.category,
            title=item.title,
            prompt=item.prompt,
        )
        for item in service.list_scenarios()
    ]


@router.post("/run", response_model=EvalRunResponse)
async def run_scenario(
    payload: EvalRunRequest,
    service: EvalService = Depends(get_eval_service),
) -> EvalRunResponse:
    try:
        result = service.run_scenario(payload.scenario_id, model=payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_run_response(result)


@router.post("/run-suite", response_model=EvalSuiteRunResponse)
async def run_suite(
    payload: EvalSuiteRunRequest,
    service: EvalService = Depends(get_eval_service),
) -> EvalSuiteRunResponse:
    report = service.run_suite(
        category=payload.category,
        limit=payload.limit,
        persist_report=payload.persist_report,
        model=payload.model,
    )
    return EvalSuiteRunResponse(
        run_id=str(report["run_id"]),
        started_at=float(report["started_at"]),
        finished_at=float(report["finished_at"]),
        total=int(report["total"]),
        passed=int(report["passed"]),
        failed=int(report["failed"]),
        pass_rate=float(report["pass_rate"]),
        category_filter=str(report["category_filter"]) if report.get("category_filter") else None,
        results=[_to_run_response(item) for item in report["results"]],
    )


@router.get("/dashboard", response_model=EvalDashboardResponse)
async def eval_dashboard(
    limit: int = 10,
    service: EvalService = Depends(get_eval_service),
) -> EvalDashboardResponse:
    payload = service.build_dashboard(report_limit=max(1, min(limit, 50)))
    return EvalDashboardResponse(**payload)


@router.get("/reports", response_model=EvalReportSummaryResponse)
async def list_reports(
    limit: int = 10,
    service: EvalService = Depends(get_eval_service),
) -> EvalReportSummaryResponse:
    reports = service.list_reports(limit=limit)
    return EvalReportSummaryResponse(reports=reports, total=len(reports))


@router.post("/run-suite/{tier}", response_model=EvalSuiteRunResponse)
async def run_suite_tier(
    tier: str,
    service: EvalService = Depends(get_eval_service),
) -> EvalSuiteRunResponse:
    gate_map = {
        "fast": FAST_GATE,
        "deep": DEEP_GATE,
        "release": RELEASE_GATE,
    }
    selected = gate_map.get(tier.strip().lower())
    if selected is None:
        raise HTTPException(status_code=404, detail=f"Unknown eval tier: {tier}")
    report = service.run_suite(
        limit=None if selected.limit <= 0 else selected.limit,
        persist_report=True,
    )
    ok, detail = evaluate_tier_gate(
        tier=selected,
        pass_rate=float(report["pass_rate"]),
        total=int(report["total"]),
        quality_median=float(report.get("quality_median", 0.0) or 0.0) or None,
        cloud_judge_coverage=float(report.get("cloud_judge_coverage", 0.0) or 0.0),
    )
    if not ok:
        raise HTTPException(status_code=412, detail=detail)
    return EvalSuiteRunResponse(
        run_id=str(report["run_id"]),
        started_at=float(report["started_at"]),
        finished_at=float(report["finished_at"]),
        total=int(report["total"]),
        passed=int(report["passed"]),
        failed=int(report["failed"]),
        pass_rate=float(report["pass_rate"]),
        category_filter=str(report["category_filter"]) if report.get("category_filter") else None,
        results=[_to_run_response(item) for item in report["results"]],
    )


@router.post("/run-suite/model-bound/{tier}", response_model=EvalSuiteRunResponse)
async def run_model_bound_suite(
    tier: str,
    service: EvalService = Depends(get_eval_service),
) -> EvalSuiteRunResponse:
    gate_map = {
        "model_bound_ci": MODEL_BOUND_CI_GATE,
        "model_bound_release": MODEL_BOUND_RELEASE_GATE,
    }
    selected = gate_map.get(tier.strip().lower())
    if selected is None:
        raise HTTPException(status_code=404, detail=f"Unknown model-bound eval tier: {tier}")
    if selected.name == MODEL_BOUND_CI_GATE.name:
        scenario_ids = service.model_bound_tool_scenario_ids()
    else:
        scenario_ids = service.model_bound_scenario_ids()
    if not scenario_ids:
        raise HTTPException(status_code=404, detail="No model-bound scenarios configured")
    report = service.run_scenario_ids(
        scenario_ids,
        persist_report=True,
        category_filter="model_bound",
    )
    ok, detail = evaluate_tier_gate(
        tier=selected,
        pass_rate=float(report["pass_rate"]),
        total=int(report["total"]),
        quality_median=float(report.get("quality_median", 0.0) or 0.0) or None,
        cloud_judge_coverage=float(report.get("cloud_judge_coverage", 0.0) or 0.0),
    )
    if not ok:
        raise HTTPException(status_code=412, detail=detail)
    return EvalSuiteRunResponse(
        run_id=str(report["run_id"]),
        started_at=float(report["started_at"]),
        finished_at=float(report["finished_at"]),
        total=int(report["total"]),
        passed=int(report["passed"]),
        failed=int(report["failed"]),
        pass_rate=float(report["pass_rate"]),
        category_filter=str(report["category_filter"]) if report.get("category_filter") else None,
        results=[_to_run_response(item) for item in report["results"]],
    )


@router.post("/benchmark/baselines", response_model=EvalBenchmarkResponse)
async def run_benchmark_baselines(
    payload: EvalBenchmarkRequest,
    service: EvalService = Depends(get_eval_service),
) -> EvalBenchmarkResponse:
    settings = get_settings()
    if payload.scenario_ids:
        scenario_ids = payload.scenario_ids
    elif payload.use_model_benchmarks and service.model_benchmark_scenario_ids():
        scenario_ids = service.model_benchmark_scenario_ids()
    else:
        scenario_ids = ["IQ1", "SWE1", "A1"]
    reference_model = resolve_benchmark_reference_model(settings)
    benchmark = EvalBenchmarkService(
        report_file_path=settings.eval_report_file_path,
        termit_model=settings.code_model,
        reference_model=reference_model,
        scenario_runner=lambda scenario_id, model: service.run_scenario(scenario_id, model=model),
        quality_judge=lambda result: float(result.get("quality_score", 0.0) or 0.0),
    )
    report = benchmark.compare_on_scenarios(scenario_ids, persist=payload.persist)
    routing_sync: dict[str, object] | None = None
    if payload.sync_routing:
        routing_sync = _sync_routing_from_benchmark(
            report=report,
            service=service,
            blend_alpha=payload.blend_alpha,
            persist=True,
            dry_run=False,
        )
    return EvalBenchmarkResponse(
        benchmark_id=str(report["benchmark_id"]),
        termit_model=str(report["termit_model"]),
        reference_model=str(report["reference_model"]),
        termit_pass_rate=float(report["termit_pass_rate"]),
        reference_pass_rate=float(report["reference_pass_rate"]),
        termit_quality_mean=float(report["termit_quality_mean"]),
        reference_quality_mean=float(report["reference_quality_mean"]),
        rows=list(report.get("rows", [])),
        routing_sync=routing_sync,
    )


@router.get("/benchmark/capability-review", response_model=EvalCapabilityReviewResponse)
async def benchmark_capability_review(limit: int = 6) -> EvalCapabilityReviewResponse:
    settings = get_settings()
    reference_model = resolve_benchmark_reference_model(settings)
    benchmark = EvalBenchmarkService(
        report_file_path=settings.eval_report_file_path,
        termit_model=settings.code_model,
        reference_model=reference_model,
    )
    payload = benchmark.build_capability_review(limit=max(1, min(limit, 52)))
    return EvalCapabilityReviewResponse(**payload)


@router.get("/benchmark/capability-regression", response_model=EvalCapabilityRegressionResponse)
async def benchmark_capability_regression(
    limit: int = 6,
    baseline_path: str | None = None,
    max_pass_gap_drop: float | None = None,
    max_quality_gap_drop: float | None = None,
    max_win_rate_drop: float | None = None,
) -> EvalCapabilityRegressionResponse:
    settings = get_settings()
    baseline_file = Path((baseline_path or settings.eval_capability_baseline_path).strip())
    if not baseline_file.exists():
        raise HTTPException(status_code=404, detail=f"Capability baseline not found: {baseline_file}")
    try:
        baseline_payload = json.loads(baseline_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid capability baseline JSON: {baseline_file}") from exc
    if not isinstance(baseline_payload, dict):
        raise HTTPException(status_code=400, detail=f"Capability baseline must be JSON object: {baseline_file}")

    reference_model = resolve_benchmark_reference_model(settings)
    benchmark = EvalBenchmarkService(
        report_file_path=settings.eval_report_file_path,
        termit_model=settings.code_model,
        reference_model=reference_model,
    )
    payload = benchmark.build_capability_regression(
        baseline=baseline_payload,
        limit=max(1, min(limit, 52)),
        max_pass_gap_drop=(
            settings.capability_regression_max_pass_gap_drop
            if max_pass_gap_drop is None
            else max(0.0, float(max_pass_gap_drop))
        ),
        max_quality_gap_drop=(
            settings.capability_regression_max_quality_gap_drop
            if max_quality_gap_drop is None
            else max(0.0, float(max_quality_gap_drop))
        ),
        max_win_rate_drop=(
            settings.capability_regression_max_win_rate_drop
            if max_win_rate_drop is None
            else max(0.0, float(max_win_rate_drop))
        ),
    )
    return EvalCapabilityRegressionResponse(**payload)


@router.post("/benchmark/capability-baseline/refresh", response_model=EvalCapabilityBaselineRefreshResponse)
async def refresh_capability_baseline(
    limit: int = 12,
    baseline_path: str | None = None,
) -> EvalCapabilityBaselineRefreshResponse:
    settings = get_settings()
    target_path = (baseline_path or settings.eval_capability_baseline_path).strip()
    reference_model = resolve_benchmark_reference_model(settings)
    benchmark = EvalBenchmarkService(
        report_file_path=settings.eval_report_file_path,
        termit_model=settings.code_model,
        reference_model=reference_model,
    )
    baseline = benchmark.refresh_capability_baseline(
        baseline_file_path=target_path,
        limit=max(1, min(limit, 52)),
    )
    return EvalCapabilityBaselineRefreshResponse(
        baseline_path=target_path,
        baseline=baseline,
    )


@router.post("/benchmark/sync-routing", response_model=RoutingBenchmarkSyncResponse)
async def sync_routing_benchmarks(
    payload: RoutingBenchmarkSyncRequest,
    service: EvalService = Depends(get_eval_service),
) -> RoutingBenchmarkSyncResponse:
    settings = get_settings()
    sync = RoutingBenchmarkSyncService(
        get_routing_policy_service(),
        report_file_path=settings.eval_report_file_path,
    )
    categories = _scenario_category_map(service)
    try:
        if payload.benchmark_report is not None:
            summary = sync.sync_from_report(
                payload.benchmark_report,
                category_by_scenario_id=categories,
                blend_alpha=payload.blend_alpha,
                persist=payload.persist,
                dry_run=payload.dry_run,
            )
        elif payload.from_latest:
            summary = sync.sync_from_latest_report(
                category_by_scenario_id=categories,
                blend_alpha=payload.blend_alpha,
                persist=payload.persist,
                dry_run=payload.dry_run,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide benchmark_report or set from_latest=true.",
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RoutingBenchmarkSyncResponse(
        dry_run=bool(summary.get("dry_run")),
        benchmark_id=str(summary["benchmark_id"]) if summary.get("benchmark_id") else None,
        updated_models=list(summary.get("updated_models", [])),
        computed_scores=dict(summary.get("computed_scores", {})),
        blend_alpha=float(summary.get("blend_alpha", payload.blend_alpha)),
        synced_at=str(summary["synced_at"]) if summary.get("synced_at") else None,
    )
