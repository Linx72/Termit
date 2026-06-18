"""Capability gate tier presets (CI-safe vs release thresholds)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityGateTier:
    name: str
    min_reports: int
    min_pass_gap: float
    min_quality_gap: float
    min_win_rate: float
    allowed_trends: str
    max_pass_gap_drop: float
    max_quality_gap_drop: float
    max_win_rate_drop: float


CI_GATE = CapabilityGateTier(
    name="ci",
    min_reports=1,
    min_pass_gap=-1.0,
    min_quality_gap=-1.0,
    min_win_rate=0.0,
    allowed_trends="flat,improving,regressing,no_data",
    max_pass_gap_drop=0.05,
    max_quality_gap_drop=0.05,
    max_win_rate_drop=0.10,
)

NIGHTLY_GATE = CI_GATE

RELEASE_GATE = CapabilityGateTier(
    name="release",
    min_reports=2,
    min_pass_gap=-0.05,
    min_quality_gap=-0.10,
    min_win_rate=0.40,
    allowed_trends="flat,improving",
    max_pass_gap_drop=0.05,
    max_quality_gap_drop=0.05,
    max_win_rate_drop=0.10,
)

TIER_MAP: dict[str, CapabilityGateTier] = {
    "ci": CI_GATE,
    "nightly": NIGHTLY_GATE,
    "release": RELEASE_GATE,
}


def apply_capability_gate_tier(tier_name: str, *, overwrite: bool = False) -> CapabilityGateTier | None:
    """Apply tier defaults to process env unless keys are already set."""
    tier = TIER_MAP.get(tier_name.strip().lower())
    if tier is None:
        return None
    values = {
        "TERMIT_CAP_MIN_REPORTS": str(tier.min_reports),
        "TERMIT_CAP_MIN_MEAN_PASS_GAP": str(tier.min_pass_gap),
        "TERMIT_CAP_MIN_MEAN_QUALITY_GAP": str(tier.min_quality_gap),
        "TERMIT_CAP_MIN_WIN_RATE": str(tier.min_win_rate),
        "TERMIT_CAP_ALLOWED_TRENDS": tier.allowed_trends,
        "TERMIT_CAP_REG_MAX_PASS_GAP_DROP": str(tier.max_pass_gap_drop),
        "TERMIT_CAP_REG_MAX_QUALITY_GAP_DROP": str(tier.max_quality_gap_drop),
        "TERMIT_CAP_REG_MAX_WIN_RATE_DROP": str(tier.max_win_rate_drop),
    }
    for key, value in values.items():
        if overwrite or key not in os.environ:
            os.environ[key] = value
    return tier
