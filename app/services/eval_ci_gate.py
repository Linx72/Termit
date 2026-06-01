from __future__ import annotations

from typing import Optional


def evaluate_ci_gate(
    *,
    pass_rate: float,
    min_rate: float,
    total: int,
) -> tuple[bool, str]:
    if total <= 0:
        return False, "Eval suite executed zero scenarios."
    if pass_rate + 1e-9 < min_rate:
        return (
            False,
            f"Eval pass_rate {pass_rate:.4f} is below minimum {min_rate:.4f} ({total} scenarios).",
        )
    return True, f"Eval gate passed: pass_rate={pass_rate:.4f}, total={total}."


def evaluate_finetune_delta_gate(
    *,
    baseline_pass_rate: Optional[float],
    post_pass_rate: float,
    total: int,
    min_delta: float = 0.0,
    min_rate: Optional[float] = None,
) -> tuple[bool, str]:
    if total <= 0:
        return False, "Post-finetune eval executed zero scenarios."

    if min_rate is not None and post_pass_rate + 1e-9 < min_rate:
        return (
            False,
            f"Post-finetune pass_rate {post_pass_rate:.4f} below minimum {min_rate:.4f}.",
        )

    if baseline_pass_rate is None:
        return (
            True,
            f"No baseline; post-finetune pass_rate={post_pass_rate:.4f}, total={total}.",
        )

    delta = post_pass_rate - baseline_pass_rate
    if delta + 1e-9 < min_delta:
        return (
            False,
            (
                f"Finetune regression: delta {delta:+.4f} "
                f"(post={post_pass_rate:.4f}, baseline={baseline_pass_rate:.4f})."
            ),
        )

    return (
        True,
        (
            f"Finetune delta gate passed: delta {delta:+.4f} "
            f"(post={post_pass_rate:.4f}, baseline={baseline_pass_rate:.4f}, total={total})."
        ),
    )
