from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.eval_service import EvalService


class EvalDashboardTests(unittest.TestCase):
    def test_pass_rate_by_category(self) -> None:
        rates = EvalService.pass_rate_by_category(
            [
                {"category": "cursor_parity", "status": "passed"},
                {"category": "cursor_parity", "status": "failed"},
                {"category": "coding", "status": "passed"},
            ]
        )
        self.assertAlmostEqual(rates["cursor_parity"], 0.5)
        self.assertAlmostEqual(rates["coding"], 1.0)

    def test_build_dashboard_includes_kpi_fields(self) -> None:
        service = EvalService(scenarios_path="data/eval_scenarios.json")
        dashboard = service.build_dashboard(report_limit=3)
        self.assertIn("pass_rate", dashboard)
        self.assertIn("pass_rate_by_category", dashboard)
        self.assertIn("latency_p95_ms", dashboard)
        self.assertIn("estimated_cost_usd", dashboard)
        self.assertIn("scenario_count", dashboard)
        self.assertGreaterEqual(int(dashboard["scenario_count"]), 54)

    def test_eval_dashboard_api(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.routes.eval import router as eval_router
        from app.state import get_eval_service

        app = FastAPI()
        app.include_router(eval_router)
        app.dependency_overrides[get_eval_service] = lambda: EvalService(
            scenarios_path="data/eval_scenarios.json"
        )
        client = TestClient(app)
        response = client.get("/api/eval/dashboard?limit=3")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["scenario_count"], 54)

    def test_capability_review_api_reads_benchmark_history(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.routes.eval import router as eval_router

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "eval_reports.jsonl"
            report_path.write_text(
                json.dumps(
                    {
                        "benchmark_id": "bench_42",
                        "timestamp": "2026-06-10T00:00:00Z",
                        "termit_pass_rate": 0.75,
                        "reference_pass_rate": 0.65,
                        "termit_quality_mean": 0.8,
                        "reference_quality_mean": 0.7,
                        "rows": [{"scenario_id": "MB1", "status": "passed"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            app = FastAPI()
            app.include_router(eval_router)
            fake_settings = type(
                "FakeSettings",
                (),
                {
                    "eval_report_file_path": str(report_path),
                    "code_model": "ollama:termit-core-ft",
                    "eval_benchmark_reference_model": "openai_compat:deepseek-ai/DeepSeek-V3",
                },
            )()
            with patch("app.api.routes.eval.get_settings", return_value=fake_settings):
                client = TestClient(app)
                response = client.get("/api/eval/benchmark/capability-review?limit=4")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["total_reports"], 1)
            self.assertEqual(payload["latest_benchmark_id"], "bench_42")
            self.assertEqual(payload["trend_direction"], "flat")

    def test_capability_regression_api_returns_gate_payload(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.routes.eval import router as eval_router

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "eval_reports.jsonl"
            report_path.write_text(
                json.dumps(
                    {
                        "benchmark_id": "bench_99",
                        "timestamp": "2026-06-10T00:00:00Z",
                        "termit_pass_rate": 0.80,
                        "reference_pass_rate": 0.70,
                        "termit_quality_mean": 0.70,
                        "reference_quality_mean": 0.60,
                        "rows": [{"scenario_id": "MB1", "status": "passed"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            baseline_path = Path(tmp) / "baseline.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "total_reports": 1,
                        "mean_pass_gap": 0.00,
                        "mean_quality_gap": 0.00,
                        "termit_win_rate": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            app = FastAPI()
            app.include_router(eval_router)
            fake_settings = type(
                "FakeSettings",
                (),
                {
                    "eval_report_file_path": str(report_path),
                    "code_model": "ollama:termit-core-ft",
                    "eval_benchmark_reference_model": "openai_compat:deepseek-ai/DeepSeek-V3",
                    "eval_capability_baseline_path": str(baseline_path),
                    "capability_regression_max_pass_gap_drop": 0.05,
                    "capability_regression_max_quality_gap_drop": 0.05,
                    "capability_regression_max_win_rate_drop": 0.10,
                },
            )()
            with patch("app.api.routes.eval.get_settings", return_value=fake_settings):
                client = TestClient(app)
                response = client.get("/api/eval/benchmark/capability-regression?limit=4")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(bool(payload["gate_passed"]))
            self.assertEqual(payload["required_min_reports"], 1)

    def test_refresh_capability_baseline_api_writes_file(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.routes.eval import router as eval_router

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "eval_reports.jsonl"
            report_path.write_text(
                json.dumps(
                    {
                        "benchmark_id": "bench_100",
                        "timestamp": "2026-06-10T00:00:00Z",
                        "termit_pass_rate": 0.90,
                        "reference_pass_rate": 0.80,
                        "termit_quality_mean": 0.90,
                        "reference_quality_mean": 0.80,
                        "rows": [{"scenario_id": "MB1", "status": "passed"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            baseline_path = Path(tmp) / "baseline_refreshed.json"
            app = FastAPI()
            app.include_router(eval_router)
            fake_settings = type(
                "FakeSettings",
                (),
                {
                    "eval_report_file_path": str(report_path),
                    "code_model": "ollama:termit-core-ft",
                    "eval_benchmark_reference_model": "openai_compat:deepseek-ai/DeepSeek-V3",
                    "eval_capability_baseline_path": str(baseline_path),
                },
            )()
            with patch("app.api.routes.eval.get_settings", return_value=fake_settings):
                client = TestClient(app)
                response = client.post("/api/eval/benchmark/capability-baseline/refresh?limit=4")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["baseline_path"], str(baseline_path))
            self.assertTrue(baseline_path.exists())
            saved = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["latest_benchmark_id"], "bench_100")


if __name__ == "__main__":
    unittest.main()
