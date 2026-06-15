from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalGateTier:
    name: str
    limit: int
    min_pass_rate: float
    require_quality: bool = False
    min_quality_median: float = 0.0


FAST_GATE = EvalGateTier(name="fast", limit=12, min_pass_rate=0.90)
DEEP_GATE = EvalGateTier(name="deep", limit=53, min_pass_rate=0.95)
RELEASE_GATE = EvalGateTier(
    name="release",
    limit=0,
    min_pass_rate=0.95,
    require_quality=True,
    min_quality_median=3.0,
)


def evaluate_ci_gate(
    *,
    pass_rate: float,
    min_rate: float,
    total: int,
    quality_median: float | None = None,
    min_quality_median: float | None = None,
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
    quality_note = ""
    if quality_median is not None:
        quality_note = f", quality_median={quality_median:.3f}"
    return True, f"Eval gate passed: pass_rate={pass_rate:.4f}, total={total}{quality_note}."


def evaluate_tier_gate(
    *,
    tier: EvalGateTier,
    pass_rate: float,
    total: int,
    quality_median: float | None = None,
) -> tuple[bool, str]:
    min_quality = tier.min_quality_median if tier.require_quality else None
    return evaluate_ci_gate(
        pass_rate=pass_rate,
        min_rate=tier.min_pass_rate,
        total=total,
        quality_median=quality_median,
        min_quality_median=min_quality,
    )
