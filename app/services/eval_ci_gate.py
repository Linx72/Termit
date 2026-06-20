from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalGateTier:
    name: str
    limit: int
    min_pass_rate: float
    require_quality: bool = False
    min_quality_median: float = 0.0
    require_cloud_judge: bool = False
    min_cloud_judge_coverage: float = 0.0


FAST_GATE = EvalGateTier(name="fast", limit=12, min_pass_rate=0.90)
DEEP_GATE = EvalGateTier(name="deep", limit=53, min_pass_rate=0.95)
RELEASE_GATE = EvalGateTier(
    name="release",
    limit=0,
    min_pass_rate=0.95,
    require_quality=True,
    min_quality_median=3.0,
    require_cloud_judge=True,
    min_cloud_judge_coverage=1.0,
)

# Deterministic tool scenarios (HumanEval/MBPP/SWE/Terminal fixtures) — safe for CI without cloud keys.
MODEL_BOUND_CI_GATE = EvalGateTier(
    name="model_bound_ci",
    limit=0,
    min_pass_rate=1.0,
)

# Full model-bound slice: model_benchmark + humaneval/mbpp tool runners.
MODEL_BOUND_RELEASE_GATE = EvalGateTier(
    name="model_bound_release",
    limit=0,
    min_pass_rate=0.80,
    require_quality=True,
    min_quality_median=2.5,
    require_cloud_judge=True,
    min_cloud_judge_coverage=0.5,
)


def evaluate_ci_gate(
    *,
    pass_rate: float,
    min_rate: float,
    total: int,
    quality_median: float | None = None,
    min_quality_median: float | None = None,
    cloud_judge_coverage: float | None = None,
    min_cloud_judge_coverage: float | None = None,
) -> tuple[bool, str]:
    if total <= 0:
        return False, "Eval suite executed zero scenarios."
    if pass_rate + 1e-9 < min_rate:
        return (
            False,
            f"Eval pass_rate {pass_rate:.4f} is below minimum {min_rate:.4f} ({total} scenarios).",
        )
    if min_quality_median is not None and quality_median is not None:
        if quality_median + 1e-9 < min_quality_median:
            return (
                False,
                f"Eval quality_median {quality_median:.3f} is below minimum {min_quality_median:.3f}.",
            )
    if min_cloud_judge_coverage is not None:
        if cloud_judge_coverage is None:
            return False, "Eval gate requires cloud judge coverage but report has no coverage metric."
        if cloud_judge_coverage + 1e-9 < min_cloud_judge_coverage:
            return (
                False,
                "Eval cloud_judge_coverage "
                f"{cloud_judge_coverage:.4f} is below minimum {min_cloud_judge_coverage:.4f}.",
            )
    quality_note = ""
    if quality_median is not None:
        quality_note = f", quality_median={quality_median:.3f}"
    coverage_note = ""
    if cloud_judge_coverage is not None:
        coverage_note = f", cloud_judge_coverage={cloud_judge_coverage:.4f}"
    return (
        True,
        f"Eval gate passed: pass_rate={pass_rate:.4f}, total={total}{quality_note}{coverage_note}.",
    )


def evaluate_tier_gate(
    *,
    tier: EvalGateTier,
    pass_rate: float,
    total: int,
    quality_median: float | None = None,
    cloud_judge_coverage: float | None = None,
) -> tuple[bool, str]:
    min_quality = tier.min_quality_median if tier.require_quality else None
    min_cloud_coverage = tier.min_cloud_judge_coverage if tier.require_cloud_judge else None
    return evaluate_ci_gate(
        pass_rate=pass_rate,
        min_rate=tier.min_pass_rate,
        total=total,
        quality_median=quality_median,
        min_quality_median=min_quality,
        cloud_judge_coverage=cloud_judge_coverage,
        min_cloud_judge_coverage=min_cloud_coverage,
    )
