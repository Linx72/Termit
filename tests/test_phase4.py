import tempfile
import unittest
from pathlib import Path

from app.services.eval_service import EvalService
from app.services.finetune_adapter_resolver import FinetuneAdapterResolver


class EvalDashboardTests(unittest.TestCase):
    def test_build_dashboard_from_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_path = Path(tmp) / "reports.jsonl"
            reports_path.write_text(
                '{"run_id":"e1","pass_rate":0.9,"total":10,"passed":9,'
                '"latency_p95_ms":120,"estimated_cost_usd":0.0012}\n',
                encoding="utf-8",
            )
            from app.services.eval_report_store import EvalReportStore

            service = EvalService(
                scenarios_path=str(Path("./data/eval_scenarios.json")),
                report_store=EvalReportStore(str(reports_path)),
            )
            dashboard = service.build_dashboard(report_limit=1)
            self.assertEqual(dashboard["pass_rate"], 0.9)
            self.assertEqual(dashboard["latency_p95_ms"], 120)
            self.assertAlmostEqual(float(dashboard["estimated_cost_usd"]), 0.0012)


class FinetuneAdapterResolverTests(unittest.TestCase):
    def test_filesystem_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = Path(tmp) / "termit-core"
            repo_dir.mkdir()
            (repo_dir / "adapter.gguf").write_bytes(b"fake")
            resolver = FinetuneAdapterResolver(
                adapters_path=str(Path(tmp) / "missing.json"),
                adapters_dir=str(tmp),
            )
            model = resolver.resolve_model("termit-core")
            self.assertEqual(model, "ollama:termit-core-ft")


if __name__ == "__main__":
    unittest.main()
