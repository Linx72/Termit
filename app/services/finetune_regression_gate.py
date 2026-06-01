from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RegressionDecision:
    promote: bool
    use_shadow: bool
    baseline_pass_rate: Optional[float]
    post_pass_rate: Optional[float]
    delta: Optional[float]
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "promote": self.promote,
            "use_shadow": self.use_shadow,
            "baseline_pass_rate": self.baseline_pass_rate,
            "post_pass_rate": self.post_pass_rate,
            "delta": self.delta,
            "reason": self.reason,
        }


def evaluate_training_regression(
    *,
    baseline_pass_rate: Optional[float],
    post_pass_rate: Optional[float],
    max_regression: float = 0.02,
    shadow_on_regression: bool = True,
    require_post_eval: bool = False,
) -> RegressionDecision:
    if post_pass_rate is None:
        if require_post_eval:
            return RegressionDecision(
                promote=False,
                use_shadow=False,
                baseline_pass_rate=baseline_pass_rate,
                post_pass_rate=None,
                delta=None,
                reason="Post-train eval missing; promotion blocked (require_post_eval).",
            )
        return RegressionDecision(
            promote=True,
            use_shadow=False,
            baseline_pass_rate=baseline_pass_rate,
            post_pass_rate=None,
            delta=None,
            reason="Post-train eval missing; promotion allowed (no regression data).",
        )
    if baseline_pass_rate is None:
        return RegressionDecision(
            promote=True,
            use_shadow=False,
            baseline_pass_rate=None,
            post_pass_rate=post_pass_rate,
            delta=None,
            reason="Baseline eval missing; promotion allowed.",
        )

    delta = post_pass_rate - baseline_pass_rate
    if delta < -abs(max_regression):
        if shadow_on_regression:
            return RegressionDecision(
                promote=False,
                use_shadow=True,
                baseline_pass_rate=baseline_pass_rate,
                post_pass_rate=post_pass_rate,
                delta=delta,
                reason=(
                    f"Regression detected ({post_pass_rate:.2%} vs baseline {baseline_pass_rate:.2%}); "
                    "model registered as shadow only."
                ),
            )
        return RegressionDecision(
            promote=False,
            use_shadow=False,
            baseline_pass_rate=baseline_pass_rate,
            post_pass_rate=post_pass_rate,
            delta=delta,
            reason=(
                f"Regression detected ({post_pass_rate:.2%} vs baseline {baseline_pass_rate:.2%}); "
                "adapter registration blocked."
            ),
        )

    return RegressionDecision(
        promote=True,
        use_shadow=False,
        baseline_pass_rate=baseline_pass_rate,
        post_pass_rate=post_pass_rate,
        delta=delta,
        reason=f"Pass rate improved or within tolerance (delta {delta:+.2%}).",
    )
