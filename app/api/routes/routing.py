from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.schemas import (
    RepoModelProfileResponse,
    RoutingBenchmarkScoreResponse,
    RoutingPolicyInfoResponse,
)
from app.services.routing_policy_service import RoutingPolicyService
from app.domain.schemas import TaskType
from app.state import get_routing_policy_service

router = APIRouter(prefix="/api/routing", tags=["routing"])


@router.get("/profiles", response_model=list[RepoModelProfileResponse])
async def list_repo_profiles(
    service: RoutingPolicyService = Depends(get_routing_policy_service),
) -> list[RepoModelProfileResponse]:
    return [
        RepoModelProfileResponse(
            profile_id=item.profile_id,
            title=item.title,
            path_prefix=item.path_prefix,
            task_type=item.task_type,
            preferred_model=item.preferred_model,
            description=item.description,
        )
        for item in service.list_repo_profiles()
    ]


@router.get("/profiles/{profile_id}", response_model=RepoModelProfileResponse)
async def get_repo_profile(
    profile_id: str,
    service: RoutingPolicyService = Depends(get_routing_policy_service),
) -> RepoModelProfileResponse:
    profile = service.get_repo_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Unknown repo profile: {profile_id}")
    return RepoModelProfileResponse(
        profile_id=profile.profile_id,
        title=profile.title,
        path_prefix=profile.path_prefix,
        task_type=profile.task_type,
        preferred_model=profile.preferred_model,
        description=profile.description,
    )


@router.get("/benchmarks", response_model=list[RoutingBenchmarkScoreResponse])
async def list_benchmark_scores(
    task_type: TaskType = Query(default=TaskType.coding),
    service: RoutingPolicyService = Depends(get_routing_policy_service),
) -> list[RoutingBenchmarkScoreResponse]:
    models = service.list_benchmark_models()
    scores: list[RoutingBenchmarkScoreResponse] = []
    for model in models:
        score = service.benchmark_score(model, task_type)
        if score is None:
            continue
        scores.append(
            RoutingBenchmarkScoreResponse(
                model=model,
                task_type=task_type.value,
                score=round(score, 4),
            )
        )
    scores.sort(key=lambda item: item.score, reverse=True)
    return scores


@router.get("/policy", response_model=RoutingPolicyInfoResponse)
async def routing_policy_info(
    service: RoutingPolicyService = Depends(get_routing_policy_service),
) -> RoutingPolicyInfoResponse:
    return RoutingPolicyInfoResponse(
        repo_profiles=[
            RepoModelProfileResponse(
                profile_id=item.profile_id,
                title=item.title,
                path_prefix=item.path_prefix,
                task_type=item.task_type,
                preferred_model=item.preferred_model,
                description=item.description,
            )
            for item in service.list_repo_profiles()
        ],
        benchmark_models=service.list_benchmark_models(),
    )
