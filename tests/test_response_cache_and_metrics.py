import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.response_cache_store import ResponseCacheStore
from app.services.telemetry_store import TelemetryStore


class ResponseCacheStoreTests(unittest.TestCase):
    def test_memory_cache_roundtrip(self) -> None:
        store = ResponseCacheStore(backend="memory")
        store.set("k", '{"ok":1}', ttl_seconds=10)
        self.assertEqual(store.get("k"), '{"ok":1}')

    def test_sqlite_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cache.db"
            store = ResponseCacheStore(backend="sqlite", sqlite_path=str(db))
            store.set("k2", '{"ok":2}', ttl_seconds=10)
            self.assertEqual(store.get("k2"), '{"ok":2}')


class TelemetryStoreTests(unittest.TestCase):
    def test_snapshot_rates(self) -> None:
        store = TelemetryStore()
        store.record_chat(
            success=True,
            cache_hit=True,
            latency_ms=100,
            selected_model="ollama:code",
            estimated_cost_usd=0.01,
            response_text="```python\nprint('ok')\n```",
            fallback_used=False,
        )
        store.record_chat(
            success=False,
            cache_hit=False,
            latency_ms=200,
            selected_model=None,
            estimated_cost_usd=0.0,
            response_text="",
            fallback_used=False,
        )
        store.record_task(completed=True, auto_mode=True, failure_class=None)
        store.record_task(completed=False, auto_mode=True, failure_class="external_error")
        snap = store.snapshot()
        self.assertEqual(snap.chat_requests_total, 2)
        self.assertEqual(snap.chat_cache_hits_total, 1)
        self.assertEqual(snap.task_total, 2)
        self.assertIn("external_error", snap.failure_classes)
        self.assertEqual(snap.chat_code_response_total, 1)
        self.assertEqual(snap.chat_empty_response_total, 0)


class MetricsSnapshotStoreTests(unittest.TestCase):
    def test_append_and_trend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(str(file_path))
            telemetry = TelemetryStore()
            telemetry.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=123,
                selected_model="ollama:code",
                estimated_cost_usd=0.001,
                response_text="ok",
                fallback_used=False,
            )
            snap = telemetry.snapshot()
            saved = store.append_snapshot(snap)
            self.assertTrue(file_path.exists())
            self.assertGreater(len(saved.captured_at), 10)

            trend = store.trend(days=7, limit=10)
            self.assertEqual(len(trend.points), 1)
            self.assertEqual(trend.points[0].chat_success_rate, snap.chat_success_rate)

    def test_daily_report_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(str(file_path))

            telemetry1 = TelemetryStore()
            telemetry1.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=200,
                selected_model="ollama:code",
                estimated_cost_usd=0.002,
                response_text="first",
                fallback_used=False,
            )
            store.append_snapshot(telemetry1.snapshot())

            telemetry2 = TelemetryStore()
            telemetry2.record_chat(
                success=True,
                cache_hit=True,
                latency_ms=100,
                selected_model="ollama:code",
                estimated_cost_usd=0.001,
                response_text="second",
                fallback_used=False,
            )
            telemetry2.record_task(completed=True, auto_mode=True, failure_class=None)
            store.append_snapshot(telemetry2.snapshot())

            report = store.daily_report(days=7, limit=10)
            self.assertEqual(report.points_count, 2)
            self.assertIsNotNone(report.delta)
            assert report.delta is not None
            self.assertGreaterEqual(report.delta.chat_cache_hit_rate_delta, 0.0)

    def test_executive_summary_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(str(file_path))

            telemetry1 = TelemetryStore()
            telemetry1.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=300,
                selected_model="ollama:code",
                estimated_cost_usd=0.01,
                response_text="baseline",
                fallback_used=False,
            )
            store.append_snapshot(telemetry1.snapshot())

            telemetry2 = TelemetryStore()
            telemetry2.record_chat(
                success=True,
                cache_hit=True,
                latency_ms=120,
                selected_model="ollama:code",
                estimated_cost_usd=0.005,
                response_text="improved",
                fallback_used=True,
            )
            telemetry2.record_task(completed=True, auto_mode=True, failure_class=None)
            store.append_snapshot(telemetry2.snapshot())

            summary = store.executive_summary(days=7, limit=10)
            self.assertIn(summary.status, {"improving", "mixed", "stable", "degraded"})
            self.assertGreaterEqual(len(summary.highlights), 1)

    def test_executive_summary_degraded_on_quality_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(str(file_path))

            baseline = TelemetryStore()
            baseline.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=120,
                selected_model="ollama:code",
                estimated_cost_usd=0.001,
                response_text="good response",
                fallback_used=False,
            )
            store.append_snapshot(baseline.snapshot())

            degraded = TelemetryStore()
            degraded.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=140,
                selected_model="ollama:code",
                estimated_cost_usd=0.001,
                response_text="",
                fallback_used=False,
            )
            degraded.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=150,
                selected_model="openai_compat:code",
                estimated_cost_usd=0.001,
                response_text="fallback-heavy",
                fallback_used=True,
            )
            degraded.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=155,
                selected_model="openai_compat:code",
                estimated_cost_usd=0.001,
                response_text="fallback-heavy-2",
                fallback_used=True,
            )
            store.append_snapshot(degraded.snapshot())

            summary = store.executive_summary(days=7, limit=10)
            self.assertEqual(summary.status, "degraded")
            self.assertTrue(any("High empty response rate" in item for item in summary.regressions))
            self.assertTrue(any("High fallback usage rate" in item for item in summary.regressions))

    def test_executive_summary_degraded_on_rolling_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(
                str(file_path),
                degrade_empty_response_rate=0.9,
                degrade_fallback_rate=0.5,
            )
            for use_fallback in [False, True, True]:
                telemetry = TelemetryStore()
                telemetry.record_chat(
                    success=True,
                    cache_hit=False,
                    latency_ms=120,
                    selected_model="ollama:code",
                    estimated_cost_usd=0.001,
                    response_text="window",
                    fallback_used=use_fallback,
                )
                store.append_snapshot(telemetry.snapshot())

            summary = store.executive_summary(days=7, limit=10)
            self.assertEqual(summary.status, "degraded")
            self.assertTrue(
                any("Rolling window degradation: fallback threshold breached" in item for item in summary.regressions)
            )

    def test_executive_summary_uses_custom_degrade_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(
                str(file_path),
                degrade_empty_response_rate=0.6,
                degrade_fallback_rate=0.1,
            )

            baseline = TelemetryStore()
            baseline.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=120,
                selected_model="ollama:code",
                estimated_cost_usd=0.001,
                response_text="baseline",
                fallback_used=False,
            )
            store.append_snapshot(baseline.snapshot())

            fallback_heavy = TelemetryStore()
            fallback_heavy.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=140,
                selected_model="openai_compat:code",
                estimated_cost_usd=0.001,
                response_text="fallback-1",
                fallback_used=True,
            )
            fallback_heavy.record_chat(
                success=True,
                cache_hit=False,
                latency_ms=145,
                selected_model="openai_compat:code",
                estimated_cost_usd=0.001,
                response_text="fallback-2",
                fallback_used=False,
            )
            store.append_snapshot(fallback_heavy.snapshot())

            summary = store.executive_summary(days=7, limit=10)
            self.assertEqual(summary.status, "degraded")
            self.assertTrue(any("threshold 10%" in item for item in summary.regressions))

    def test_slack_summary_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(str(file_path))
            telemetry = TelemetryStore()
            telemetry.record_chat(
                success=True,
                cache_hit=True,
                latency_ms=120,
                selected_model="ollama:code",
                estimated_cost_usd=0.001,
                response_text="steady",
                fallback_used=False,
            )
            store.append_snapshot(telemetry.snapshot())
            store.append_snapshot(telemetry.snapshot())
            summary = store.slack_summary(days=7, limit=10)
            self.assertIn("Termit KPI", summary.text)
            self.assertGreaterEqual(summary.bullet_count, 1)

    def test_slack_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "metrics.jsonl"
            store = MetricsSnapshotStore(str(file_path))
            telemetry = TelemetryStore()
            telemetry.record_chat(
                success=True,
                cache_hit=True,
                latency_ms=110,
                selected_model="ollama:code",
                estimated_cost_usd=0.001,
                response_text="steady",
                fallback_used=False,
            )
            store.append_snapshot(telemetry.snapshot())
            store.append_snapshot(telemetry.snapshot())
            payload = store.slack_payload(days=7, limit=10)
            self.assertIn("text", payload.payload)
            self.assertIn("mrkdwn", payload.payload)
            self.assertTrue(payload.should_notify)
            second_payload = store.slack_payload(days=7, limit=10)
            self.assertFalse(second_payload.should_notify)
            self.assertEqual(second_payload.previous_status, payload.status)


class MetricsApiTests(unittest.TestCase):
    def test_metrics_endpoint_returns_summary(self) -> None:
        client = TestClient(app)
        response = client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("chat_requests_total", body)
        self.assertIn("task_total", body)
        self.assertIn("active_thresholds", body)
        self.assertIn("degrade_empty_response_rate", body["active_thresholds"])
        self.assertIn("degrade_fallback_rate", body["active_thresholds"])
        self.assertIn("health_status", body)
        self.assertIn("health_reasons", body)

    def test_metrics_snapshot_and_trend_endpoints(self) -> None:
        client = TestClient(app)
        snap_resp = client.post("/api/metrics/snapshot")
        self.assertEqual(snap_resp.status_code, 200)
        trend_resp = client.get("/api/metrics/trend?days=7&limit=20")
        self.assertEqual(trend_resp.status_code, 200)
        self.assertIn("points", trend_resp.json())
        report_resp = client.get("/api/metrics/daily-report?days=7&limit=20")
        self.assertEqual(report_resp.status_code, 200)
        self.assertIn("points_count", report_resp.json())
        exec_resp = client.get("/api/metrics/executive-summary?days=7&limit=20")
        self.assertEqual(exec_resp.status_code, 200)
        self.assertIn("status", exec_resp.json())
        slack_resp = client.get("/api/metrics/executive-summary/slack?days=7&limit=20")
        self.assertEqual(slack_resp.status_code, 200)
        self.assertIn("text", slack_resp.json())
        slack_payload_resp = client.get("/api/metrics/executive-summary/slack/payload?days=7&limit=20")
        self.assertEqual(slack_payload_resp.status_code, 200)
        self.assertIn("payload", slack_payload_resp.json())

    def test_metrics_prometheus_endpoint(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/metrics/prometheus")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("termit_chat_requests_total", resp.text)
        self.assertIn("termit_agent_queue_size", resp.text)
        self.assertIn("termit_tool_loop_runs", resp.text)


if __name__ == "__main__":
    unittest.main()
