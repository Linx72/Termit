from fastapi import APIRouter, Depends, HTTPException

from app.domain.schemas import (
    CrossPlatformAtomicTaskInfo,
    CrossPlatformDecomposeRequest,
    CrossPlatformDecomposeResponse,
    CrossPlatformDetectStackRequest,
    CrossPlatformDetectStackResponse,
    CrossPlatformPrepareRequest,
    CrossPlatformPrepareResponse,
    CrossPlatformRecordStepRequest,
    CrossPlatformStackInfo,
    CrossPlatformStacksResponse,
)
from app.services.cross_platform_dev_service import CROSS_PLATFORM_SKILL_ID, CrossPlatformDevService
from app.services.cross_platform_plan_store import CrossPlatformPlanStore
from app.services.training_signal_store import TrainingSignalStore
from app.state import get_training_signal_store

router = APIRouter(prefix="/api/dev/cross-platform", tags=["cross-platform"])

_service = CrossPlatformDevService()
_plan_store = CrossPlatformPlanStore()


def _to_task_info(tasks) -> list[CrossPlatformAtomicTaskInfo]:
    return [
        CrossPlatformAtomicTaskInfo(
            step_id=t.step_id,
            title=t.title,
            detail=t.detail,
            platform=t.platform,
            verify_hint=t.verify_hint,
        )
        for t in tasks
    ]


def _build_decompose_response(
    profile,
    platforms,
    tasks,
    *,
    goal: str = "",
    plan_id: str = "",
) -> CrossPlatformDecomposeResponse:
    first_prompt = ""
    if tasks:
        first_prompt = _service.format_atomic_prompt(
            goal,
            profile,
            platforms,
            tasks[0],
            index=0,
            total=len(tasks),
        )
    return CrossPlatformDecomposeResponse(
        stack_id=profile.stack_id,
        stack_name=profile.name,
        agent_template_id=profile.agent_template_id,
        skill_id=CROSS_PLATFORM_SKILL_ID,
        platforms=[p.value for p in platforms],
        build_verify=profile.build_verify,
        atomic_tasks=_to_task_info(tasks),
        first_step_prompt=first_prompt,
        plan_id=plan_id,
    )


@router.get("/stacks", response_model=CrossPlatformStacksResponse)
async def list_cross_platform_stacks() -> CrossPlatformStacksResponse:
    stacks = [
        CrossPlatformStackInfo(
            stack_id=profile.stack_id,
            name=profile.name,
            description=profile.description,
            default_platforms=[p.value for p in profile.default_platforms],
            build_verify=profile.build_verify,
            agent_template_id=profile.agent_template_id,
        )
        for profile in _service.list_stacks()
    ]
    return CrossPlatformStacksResponse(stacks=stacks)


@router.post("/detect-stack", response_model=CrossPlatformDetectStackResponse)
async def detect_cross_platform_stack(
    payload: CrossPlatformDetectStackRequest,
) -> CrossPlatformDetectStackResponse:
    stack, hints = CrossPlatformDevService.detect_stack_from_repo(payload.workspace_path)
    return CrossPlatformDetectStackResponse(
        stack_id=stack.value if stack else None,
        hints=hints,
    )


@router.post("/decompose", response_model=CrossPlatformDecomposeResponse)
async def decompose_cross_platform_task(
    payload: CrossPlatformDecomposeRequest,
) -> CrossPlatformDecomposeResponse:
    stack_id = payload.stack_id
    if not stack_id and payload.workspace_path.strip():
        detected, _ = CrossPlatformDevService.detect_stack_from_repo(payload.workspace_path)
        if detected is not None:
            stack_id = detected.value

    stack = _service.get_stack(stack_id) if stack_id else None
    if stack_id and stack is None:
        raise HTTPException(status_code=400, detail=f"Unknown stack_id: {stack_id}")

    profile, platforms, tasks = _service.decompose(
        payload.goal,
        stack_id=stack_id,
        platforms=payload.platforms,
        include_game_loop=payload.include_game_loop,
    )
    plan_id = ""
    if payload.persist_plan:
        plan_id = _plan_store.save_plan(
            goal=payload.goal,
            stack_id=profile.stack_id,
            platforms=[p.value for p in platforms],
            atomic_tasks=[
                {
                    "step_id": t.step_id,
                    "title": t.title,
                    "detail": t.detail,
                    "platform": t.platform,
                    "verify_hint": t.verify_hint,
                }
                for t in tasks
            ],
        )
    return _build_decompose_response(
        profile,
        platforms,
        tasks,
        goal=payload.goal,
        plan_id=plan_id,
    )


@router.post("/prepare", response_model=CrossPlatformPrepareResponse)
async def prepare_cross_platform_step(
    payload: CrossPlatformPrepareRequest,
) -> CrossPlatformPrepareResponse:
    stack = _service.get_stack(payload.stack_id) if payload.stack_id else None
    if payload.stack_id and stack is None:
        raise HTTPException(status_code=400, detail=f"Unknown stack_id: {payload.stack_id}")

    profile, platforms, tasks = _service.decompose(
        payload.goal,
        stack_id=payload.stack_id,
        platforms=payload.platforms,
        include_game_loop=payload.include_game_loop,
    )
    if not tasks:
        raise HTTPException(status_code=400, detail="Decomposition produced no atomic tasks.")

    index = min(payload.step_index, len(tasks) - 1)
    task = tasks[index]
    prompt = _service.format_atomic_prompt(
        payload.goal,
        profile,
        platforms,
        task,
        index=index,
        total=len(tasks),
    )
    return CrossPlatformPrepareResponse(
        stack_id=profile.stack_id,
        stack_name=profile.name,
        agent_template_id=profile.agent_template_id,
        skill_id=CROSS_PLATFORM_SKILL_ID,
        platforms=[p.value for p in platforms],
        build_verify=profile.build_verify,
        step_index=index,
        step_count=len(tasks),
        step_id=task.step_id,
        step_title=task.title,
        verify_hint=task.verify_hint or profile.build_verify,
        prompt=prompt,
        atomic_tasks=_to_task_info(tasks),
    )


@router.post("/record-step")
async def record_cross_platform_step(
    payload: CrossPlatformRecordStepRequest,
    signals: TrainingSignalStore = Depends(get_training_signal_store),
) -> dict[str, bool]:
    recorded = signals.try_capture_cross_platform_step(
        goal=payload.goal,
        stack_id=payload.stack_id,
        step_id=payload.step_id,
        step_index=payload.step_index,
        verify_ok=payload.verify_ok,
        verify_detail=payload.verify_detail,
        plan_id=payload.plan_id,
    )
    if payload.plan_id and payload.verify_ok:
        _plan_store.mark_step_completed(payload.plan_id, payload.step_id)
    return {"recorded": recorded}
