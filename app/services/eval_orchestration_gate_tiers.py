"""Orchestration eval gate tier presets (CI-safe vs local tool-loop)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestrationGateTier:
    name: str
    min_pass_rate: float
    min_retry_success_rate: float
    min_total: int
    min_tool_loop_steps: int
    require_tool_loop: bool = False
    tool_loop_fallback: bool | None = None
    max_tool_loop_fallback_delta: float | None = None


CI_GATE = OrchestrationGateTier(
    name="ci",
    min_pass_rate=0.0,
    min_retry_success_rate=0.0,
    min_total=1,
    min_tool_loop_steps=0,
)

DEEP_GATE = OrchestrationGateTier(
    name="deep",
    min_pass_rate=0.0,
    min_retry_success_rate=0.0,
    min_total=3,
    min_tool_loop_steps=0,
)

RELEASE_GATE = OrchestrationGateTier(
    name="release",
    min_pass_rate=0.30,
    min_retry_success_rate=0.50,
    min_total=3,
    min_tool_loop_steps=0,
)

LOCAL_GATE = OrchestrationGateTier(
    name="local",
    min_pass_rate=0.0,
    min_retry_success_rate=0.0,
    min_total=1,
    min_tool_loop_steps=1,
    require_tool_loop=True,
)

STRICT_LIVE_GATE = OrchestrationGateTier(
    name="strict_live",
    min_pass_rate=1.0,
    min_retry_success_rate=0.0,
    min_total=1,
    min_tool_loop_steps=1,
    require_tool_loop=True,
    tool_loop_fallback=False,
    max_tool_loop_fallback_delta=0.0,
)

TIER_MAP: dict[str, OrchestrationGateTier] = {
    "ci": CI_GATE,
    "deep": DEEP_GATE,
    "release": RELEASE_GATE,
    "local": LOCAL_GATE,
    "strict_live": STRICT_LIVE_GATE,
}


def apply_orchestration_gate_tier(tier_name: str, *, overwrite: bool = False) -> OrchestrationGateTier | None:
    tier = TIER_MAP.get(tier_name.strip().lower())
    if tier is None:
        return None
    values = {
        "TERMIT_ORCH_MIN_PASS_RATE": str(tier.min_pass_rate),
        "TERMIT_ORCH_MIN_RETRY_SUCCESS_RATE": str(tier.min_retry_success_rate),
        "TERMIT_ORCH_MIN_TOTAL": str(tier.min_total),
        "TERMIT_ORCH_MIN_TOOL_LOOP_STEPS": str(tier.min_tool_loop_steps),
        "TERMIT_ORCH_REQUIRE_TOOL_LOOP": "true" if tier.require_tool_loop else "false",
    }
    for key, value in values.items():
        if overwrite or key not in os.environ:
            os.environ[key] = value
    if tier.tool_loop_fallback is not None and (overwrite or "TERMIT_ORCH_TOOL_LOOP_FALLBACK" not in os.environ):
        os.environ["TERMIT_ORCH_TOOL_LOOP_FALLBACK"] = "true" if tier.tool_loop_fallback else "false"
    if tier.max_tool_loop_fallback_delta is not None and (
        overwrite or "TERMIT_ORCH_MAX_TOOL_LOOP_FALLBACK_DELTA" not in os.environ
    ):
        os.environ["TERMIT_ORCH_MAX_TOOL_LOOP_FALLBACK_DELTA"] = str(tier.max_tool_loop_fallback_delta)
    return tier
