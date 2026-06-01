from __future__ import annotations


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
