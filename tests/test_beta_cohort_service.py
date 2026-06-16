"""Beta cohort retention metrics."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.services.beta_cohort_service import BetaCohortService


class BetaCohortServiceTests(unittest.TestCase):
    def test_d7_retention_computed(self) -> None:
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=12)).isoformat()
        recent = (now - timedelta(days=9)).isoformat()
        service = BetaCohortService(
            feedback_entries_provider=lambda: [
                {"timestamp": old, "api_key": "alpha-key", "message": "first"},
                {"timestamp": recent, "api_key": "alpha-key", "message": "back"},
            ],
            task_activity_provider=lambda: [],
            run_activity_provider=lambda: [],
        )
        metrics = service.build_metrics()
        self.assertIsNotNone(metrics["d7_retention_rate"])
        self.assertEqual(metrics["cohort_size_d7"], 1)
        self.assertEqual(metrics["retained_d7"], 1)
        self.assertEqual(metrics["d7_retention_rate"], 1.0)

    def test_feedback_store_summarize(self) -> None:
        from app.services.feedback_store import FeedbackStore

        with tempfile.TemporaryDirectory() as tmp:
            store = FeedbackStore(f"{tmp}/feedback.jsonl")
            store.append(message="Great product", rating=5, contact=None, api_key="dev-key")
            summary = store.summarize()
            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["avg_rating"], 5.0)


if __name__ == "__main__":
    unittest.main()
