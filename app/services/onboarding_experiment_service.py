"""A/B onboarding experiment — variant assignment and conversion metrics."""

from __future__ import annotations

import hashlib
import statistics
from typing import Optional


def assign_onboarding_variant(device_id: str) -> str:
    """Deterministic A/B assignment from stable device id (50/50 split)."""
    digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 2
    return "A" if bucket == 0 else "B"


class OnboardingExperimentService:
    COMPLETED_EVENTS = frozenset(
        {
            "onboarding_completed",
            "onboarding_quick_start",
            "onboarding_wizard_complete",
        }
    )

    def summarize(self, events: list[dict[str, object]]) -> dict[str, object]:
        variants: dict[str, dict[str, object]] = {
            "A": {"assigned": 0, "completed": 0, "durations_ms": []},
            "B": {"assigned": 0, "completed": 0, "durations_ms": []},
        }
        unknown_assigned = 0
        unknown_completed = 0

        for event in events:
            event_type = str(event.get("event_type", ""))
            metadata = event.get("metadata", {})
            meta = metadata if isinstance(metadata, dict) else {}
            variant = str(meta.get("variant", "")).upper()
            if event_type == "onboarding_variant_assigned":
                if variant in variants:
                    variants[variant]["assigned"] = int(variants[variant]["assigned"]) + 1
                else:
                    unknown_assigned += 1
            elif event_type in self.COMPLETED_EVENTS:
                if variant in variants:
                    variants[variant]["completed"] = int(variants[variant]["completed"]) + 1
                    duration = event.get("duration_ms")
                    if isinstance(duration, (int, float)) and duration >= 0:
                        variants[variant]["durations_ms"].append(float(duration))
                else:
                    unknown_completed += 1

        by_variant: list[dict[str, object]] = []
        for variant_id, stats in variants.items():
            assigned = int(stats["assigned"])
            completed = int(stats["completed"])
            durations = stats["durations_ms"]
            assert isinstance(durations, list)
            conversion = completed / assigned if assigned else None
            by_variant.append(
                {
                    "variant": variant_id,
                    "assigned": assigned,
                    "completed": completed,
                    "conversion_rate": conversion,
                    "median_completion_ms": (
                        int(statistics.median(durations)) if durations else None
                    ),
                }
            )

        total_assigned = sum(int(v["assigned"]) for v in by_variant) + unknown_assigned
        total_completed = sum(int(v["completed"]) for v in by_variant) + unknown_completed
        overall_conversion = total_completed / total_assigned if total_assigned else None

        return {
            "total_assigned": total_assigned,
            "total_completed": total_completed,
            "overall_conversion_rate": overall_conversion,
            "variants": by_variant,
            "unknown_assigned": unknown_assigned,
            "unknown_completed": unknown_completed,
        }

    @staticmethod
    def resolve_variant(device_id: Optional[str]) -> str:
        if not device_id or not device_id.strip():
            return "A"
        return assign_onboarding_variant(device_id.strip())
