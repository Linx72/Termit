from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.desktop_workflow_telemetry_service import DesktopWorkflowTelemetryService
from app.services.onboarding_experiment_service import OnboardingExperimentService, assign_onboarding_variant


class OnboardingExperimentTests(unittest.TestCase):
    def test_assign_variant_deterministic(self) -> None:
        self.assertEqual(assign_onboarding_variant("device-1"), assign_onboarding_variant("device-1"))
        self.assertIn(assign_onboarding_variant("device-abc"), {"A", "B"})

    def test_summarize_conversion_by_variant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = DesktopWorkflowTelemetryService(tmp)
            telemetry.record(
                event_type="onboarding_variant_assigned",
                metadata={"variant": "A"},
            )
            telemetry.record(
                event_type="onboarding_variant_assigned",
                metadata={"variant": "B"},
            )
            telemetry.record(
                event_type="onboarding_quick_start",
                metadata={"variant": "A"},
                duration_ms=1200,
                ok=True,
            )
            experiment = OnboardingExperimentService()
            summary = experiment.summarize(telemetry.list_events())
            self.assertEqual(summary["total_assigned"], 2)
            self.assertEqual(summary["total_completed"], 1)
            variants = {str(item["variant"]): item for item in summary["variants"]}
            self.assertEqual(variants["A"]["completed"], 1)
            self.assertEqual(variants["A"]["conversion_rate"], 1.0)
            self.assertEqual(variants["B"]["completed"], 0)


class OnboardingMetricsApiTests(unittest.TestCase):
    def test_onboarding_metrics_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        client.post(
            "/api/desktop/workflow-events",
            json={
                "event_type": "onboarding_variant_assigned",
                "metadata": {"variant": "A"},
            },
        )
        client.post(
            "/api/desktop/workflow-events",
            json={
                "event_type": "onboarding_wizard_complete",
                "metadata": {"variant": "A"},
                "duration_ms": 800,
                "ok": True,
            },
        )
        response = client.get("/api/desktop/onboarding-metrics")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["total_assigned"], 1)
        self.assertGreaterEqual(body["total_completed"], 1)
        self.assertTrue(body["variants"])


if __name__ == "__main__":
    unittest.main()
