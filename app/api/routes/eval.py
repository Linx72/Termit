from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    EvalDashboardResponse,
    EvalReportSummaryResponse,
    EvalRunRequest,
    EvalRunResponse,
    EvalScenarioResponse,
    EvalSuiteRunRequest,
    EvalSuiteRunResponse,
)
from app.services.eval_service import EvalService
from app.state import get_eval_service

router = APIRouter(prefix="/api/eval", tags=["eval"])


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
        result = service.run_scenario(payload.scenario_id)
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
