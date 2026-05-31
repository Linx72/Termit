from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import AsyncIterator, Optional
import asyncio
import json

from app.domain.schemas import (
    FinetuneAdapterListResponse,
    FinetuneAdapterRegisterRequest,
    FinetuneAdapterResponse,
    FinetuneDatasetExportRequest,
    FinetuneDatasetExportResponse,
    FinetuneJobCreateRequest,
    FinetuneJobListResponse,
    FinetuneJobResponse,
    FinetunePipelineStage,
    FinetunePipelineCancelResponse,
    FinetunePipelineRunListResponse,
    FinetunePipelineRunResponse,
    FinetuneRecipeResponse,
    FinetuneStage1RunRequest,
    FinetuneStage1RunResponse,
    FinetuneStage1SchedulerStatusResponse,
    FinetuneTrainRequest,
    FinetuneTrainResponse,
    FinetuneTrainingDashboardResponse,
)
from app.services.eval_service import EvalService
from app.services.finetune_service import FinetuneJobRecord, FinetuneService
from app.services.stage1_scheduler_service import Stage1SchedulerService
from app.state import get_eval_service, get_finetune_service, get_stage1_scheduler_service

router = APIRouter(prefix="/api/finetune", tags=["finetune"])

_TERMINAL_PIPELINE_STATUSES = {"completed", "failed", "cancelled"}


def _baseline_runner_factory(eval_service: EvalService):
    def baseline_runner(request_payload: FinetuneStage1RunRequest) -> dict[str, object]:
        return eval_service.run_suite(
            category=request_payload.eval_category,
            limit=request_payload.eval_limit,
            persist_report=True,
        )

    return baseline_runner


def _job_response(job: FinetuneJobRecord) -> FinetuneJobResponse:
    return FinetuneJobResponse(
        job_id=job.job_id,
        name=job.name,
        status=job.status,
        dataset_path=job.dataset_path,
        sample_count=job.sample_count,
        base_model=job.base_model,
        created_at=job.created_at,
        updated_at=job.updated_at,
        notes=job.notes,
        adapter_model=job.adapter_model,
    )


@router.post("/datasets/export", response_model=FinetuneDatasetExportResponse)
async def export_dataset(
    payload: FinetuneDatasetExportRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneDatasetExportResponse:
    try:
        result = service.export_dataset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FinetuneDatasetExportResponse(**result)


@router.get("/training/dashboard", response_model=FinetuneTrainingDashboardResponse)
async def training_dashboard(
    limit: int = Query(default=10, ge=1, le=50),
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneTrainingDashboardResponse:
    return FinetuneTrainingDashboardResponse(**service.training_dashboard(limit=limit))


@router.post("/jobs", response_model=FinetuneJobResponse)
async def create_job(
    payload: FinetuneJobCreateRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobResponse:
    job = service.create_job(
        name=payload.name,
        dataset_path=payload.dataset_path,
        sample_count=payload.sample_count,
        base_model=payload.base_model,
        notes=payload.notes,
    )
    return _job_response(job)


@router.get("/jobs", response_model=FinetuneJobListResponse)
async def list_jobs(
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobListResponse:
    return FinetuneJobListResponse(jobs=[_job_response(job) for job in service.list_jobs()])


@router.get("/jobs/{job_id}", response_model=FinetuneJobResponse)
async def get_job(
    job_id: str,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobResponse:
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown finetune job: {job_id}")
    return _job_response(job)


@router.post("/jobs/{job_id}/run", response_model=FinetuneJobResponse)
async def run_job(
    job_id: str,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneJobResponse:
    try:
        job = service.run_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(job)


@router.post("/adapters", response_model=FinetuneAdapterResponse)
async def register_adapter(
    payload: FinetuneAdapterRegisterRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneAdapterResponse:
    adapter = service.register_adapter(payload)
    return FinetuneAdapterResponse(**adapter)


@router.get("/adapters", response_model=FinetuneAdapterListResponse)
async def list_adapters(
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneAdapterListResponse:
    adapters = service.list_adapters()
    return FinetuneAdapterListResponse(
        adapters=[FinetuneAdapterResponse(**item) for item in adapters],
    )


@router.get("/recipe", response_model=FinetuneRecipeResponse)
async def training_recipe(
    base_model: str = Query(default="ollama:deepseek-coder"),
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneRecipeResponse:
    recipe = service.training_recipe(base_model)
    return FinetuneRecipeResponse(**recipe)


@router.post("/pipeline/stage1-run", response_model=FinetuneStage1RunResponse)
async def run_stage1_pipeline(
    payload: FinetuneStage1RunRequest,
    service: FinetuneService = Depends(get_finetune_service),
    eval_service: EvalService = Depends(get_eval_service),
) -> FinetuneStage1RunResponse:
    baseline_report: Optional[dict[str, object]] = None
    if payload.run_eval_baseline:
        baseline_report = eval_service.run_suite(
            category=payload.eval_category,
            limit=payload.eval_limit,
            persist_report=True,
        )

    try:
        result = service.run_stage1_pipeline(payload, baseline_report=baseline_report)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FinetuneStage1RunResponse(
        pipeline_id=str(result["pipeline_id"]),
        status=str(result["status"]),
        created_at=str(result["created_at"]),
        dataset=FinetuneDatasetExportResponse(**result["dataset"]),
        baseline_run_id=result.get("baseline_run_id"),
        baseline_pass_rate=result.get("baseline_pass_rate"),
        baseline_total=result.get("baseline_total"),
        baseline_passed=result.get("baseline_passed"),
        job=FinetuneJobResponse(**result["job"]),
        recipe=FinetuneRecipeResponse(**result["recipe"]),
        adapter=FinetuneAdapterResponse(**result["adapter"]) if result.get("adapter") else None,
        stages=[FinetunePipelineStage(**stage) for stage in result.get("stages", [])],
    )


@router.post("/pipeline/stage1-runs", response_model=FinetunePipelineRunResponse)
async def enqueue_stage1_pipeline_run(
    payload: FinetuneStage1RunRequest,
    background_tasks: BackgroundTasks,
    service: FinetuneService = Depends(get_finetune_service),
    eval_service: EvalService = Depends(get_eval_service),
) -> FinetunePipelineRunResponse:
    queued = service.enqueue_stage1_pipeline(payload)

    background_tasks.add_task(
        service.drain_stage1_pipeline_queue,
        _baseline_runner_factory(eval_service),
    )
    return FinetunePipelineRunResponse(**queued)


@router.get("/pipeline/stage1-runs", response_model=FinetunePipelineRunListResponse)
async def list_stage1_pipeline_runs(
    limit: int = Query(default=20, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetunePipelineRunListResponse:
    runs = service.list_stage1_pipeline_runs(limit=limit, status=status)
    return FinetunePipelineRunListResponse(
        runs=[FinetunePipelineRunResponse(**item) for item in runs],
        total=len(runs),
    )


@router.get("/pipeline/stage1-runs/{run_id}", response_model=FinetunePipelineRunResponse)
async def get_stage1_pipeline_run(
    run_id: str,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetunePipelineRunResponse:
    run = service.get_stage1_pipeline_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown stage1 pipeline run: {run_id}")
    return FinetunePipelineRunResponse(**run)


@router.get("/pipeline/stage1-runs/{run_id}/stream")
async def stream_stage1_pipeline_run(
    run_id: str,
    poll_ms: int = 400,
    timeout_seconds: int = 600,
    service: FinetuneService = Depends(get_finetune_service),
) -> StreamingResponse:
    safe_poll_seconds = max(0.1, min(poll_ms, 5000) / 1000.0)
    safe_timeout = max(5, min(timeout_seconds, 3600))

    async def event_generator() -> AsyncIterator[str]:
        last_status: str | None = None
        last_updated_at: str | None = None
        last_stage_count = -1
        deadline = asyncio.get_running_loop().time() + safe_timeout
        while True:
            now = asyncio.get_running_loop().time()
            if now >= deadline:
                yield "event: timeout\ndata: {}\n\n"
                yield "event: done\ndata: {}\n\n"
                break
            run = service.get_stage1_pipeline_run(run_id)
            if run is None:
                payload = {"detail": f"Unknown stage1 pipeline run: {run_id}"}
                yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
                yield "event: done\ndata: {}\n\n"
                break

            stage_count = len(run.get("stages") or [])
            status_value = str(run["status"])
            updated_at = str(run["updated_at"])
            changed = (
                status_value != last_status
                or updated_at != last_updated_at
                or stage_count != last_stage_count
            )
            if changed:
                yield f"event: status\ndata: {json.dumps(run, ensure_ascii=True)}\n\n"
                last_status = status_value
                last_updated_at = updated_at
                last_stage_count = stage_count

            if status_value in _TERMINAL_PIPELINE_STATUSES:
                yield "event: done\ndata: {}\n\n"
                break
            await asyncio.sleep(safe_poll_seconds)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/pipeline/stage1-runs/{run_id}/retry", response_model=FinetunePipelineRunResponse)
async def retry_stage1_pipeline_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    service: FinetuneService = Depends(get_finetune_service),
    eval_service: EvalService = Depends(get_eval_service),
) -> FinetunePipelineRunResponse:
    retried, state = service.retry_stage1_pipeline_run(run_id)
    if state == "not_found":
        raise HTTPException(status_code=404, detail=f"Unknown stage1 pipeline run: {run_id}")
    if state != "queued":
        raise HTTPException(
            status_code=400,
            detail=f"Pipeline run {run_id} is in status '{state}' and cannot be retried.",
        )
    background_tasks.add_task(
        service.drain_stage1_pipeline_queue,
        _baseline_runner_factory(eval_service),
    )
    assert retried is not None
    return FinetunePipelineRunResponse(**retried)


@router.post("/pipeline/stage1-runs/{run_id}/cancel", response_model=FinetunePipelineCancelResponse)
async def cancel_stage1_pipeline_run(
    run_id: str,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetunePipelineCancelResponse:
    cancelled, state = service.cancel_stage1_pipeline_run(run_id)
    if state == "not_found":
        raise HTTPException(status_code=404, detail=f"Unknown stage1 pipeline run: {run_id}")
    return FinetunePipelineCancelResponse(
        run_id=run_id,
        cancelled=cancelled,
        status=state,
    )


@router.post("/jobs/{job_id}/train", response_model=FinetuneTrainResponse)
async def train_job(
    job_id: str,
    payload: FinetuneTrainRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneTrainResponse:
    try:
        result = service.train_job(
            job_id,
            output_model=payload.output_model,
            trainer_mode=payload.trainer_mode,
            auto_register_adapter=payload.auto_register_adapter,
            adapter_name=payload.adapter_name,
            adapter_model=payload.adapter_model,
            repo_profile_id=payload.repo_profile_id,
            adapter_description=payload.adapter_description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    adapter = result.get("adapter")
    return FinetuneTrainResponse(
        job_id=str(result.get("job_id") or job_id),
        trainer_mode=str(result.get("trainer_mode", "")),
        status=str(result.get("status", "failed")),
        output_model=result.get("output_model"),
        modelfile_path=result.get("modelfile_path"),
        command=result.get("command"),
        detail=str(result.get("detail", "")),
        duration_ms=int(result.get("duration_ms") or 0),
        adapter=FinetuneAdapterResponse(**adapter) if adapter else None,
    )


@router.post("/pipeline/stage1-runs/{run_id}/train", response_model=FinetuneTrainResponse)
async def train_stage1_pipeline_run(
    run_id: str,
    payload: FinetuneTrainRequest,
    service: FinetuneService = Depends(get_finetune_service),
) -> FinetuneTrainResponse:
    try:
        result = service.train_from_stage1_run(
            run_id,
            output_model=payload.output_model,
            trainer_mode=payload.trainer_mode,
            auto_register_adapter=payload.auto_register_adapter,
            adapter_name=payload.adapter_name,
            adapter_model=payload.adapter_model,
            repo_profile_id=payload.repo_profile_id,
            adapter_description=payload.adapter_description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    adapter = result.get("adapter")
    return FinetuneTrainResponse(
        run_id=str(result.get("run_id") or run_id),
        job_id=str(result.get("job_id") or "") or None,
        trainer_mode=str(result.get("trainer_mode", "")),
        status=str(result.get("status", "failed")),
        output_model=result.get("output_model"),
        modelfile_path=result.get("modelfile_path"),
        command=result.get("command"),
        detail=str(result.get("detail", "")),
        duration_ms=int(result.get("duration_ms") or 0),
        adapter=FinetuneAdapterResponse(**adapter) if adapter else None,
    )


@router.get(
    "/pipeline/stage1-scheduler/status",
    response_model=FinetuneStage1SchedulerStatusResponse,
)
async def get_stage1_scheduler_status(
    scheduler: Stage1SchedulerService = Depends(get_stage1_scheduler_service),
) -> FinetuneStage1SchedulerStatusResponse:
    return FinetuneStage1SchedulerStatusResponse(**scheduler.status())


@router.post("/pipeline/stage1-scheduler/trigger", response_model=FinetunePipelineRunResponse)
async def trigger_stage1_scheduler(
    scheduler: Stage1SchedulerService = Depends(get_stage1_scheduler_service),
) -> FinetunePipelineRunResponse:
    queued = scheduler.trigger_now()
    return FinetunePipelineRunResponse(**queued)
