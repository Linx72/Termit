import unittest

from app.services.finetune_dataset_curator import CuratorConfig, curate_samples


class FinetuneDatasetCuratorTests(unittest.TestCase):
    def test_deduplicate_keeps_higher_quality(self) -> None:
        samples = [
            {
                "instruction": "Fix auth bug",
                "input": "",
                "output": "Short fix note",
                "source": "task",
                "category": "coding",
            },
            {
                "instruction": "Fix auth bug",
                "input": "tool trace",
                "output": "Detailed fix with tests and rationale",
                "source": "agent_run",
                "category": "agent",
                "trajectory": "tool trace",
            },
        ]
        curated, stats = curate_samples(samples, CuratorConfig(deduplicate=True))
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0]["source"], "agent_run")
        self.assertEqual(stats.filtered_duplicate, 1)

    def test_filters_refusal_and_too_short(self) -> None:
        samples = [
            {
                "instruction": "Do work",
                "input": "",
                "output": "I cannot help with that",
                "source": "agent_run",
                "category": "agent",
            },
            {
                "instruction": "Do work",
                "input": "",
                "output": "Implemented endpoint with tests",
                "source": "task",
                "category": "coding",
            },
        ]
        curated, stats = curate_samples(
            samples,
            CuratorConfig(skip_error_patterns=True, min_output_chars=12),
        )
        self.assertEqual(len(curated), 1)
        self.assertEqual(stats.filtered_quality, 1)
        self.assertIn("Implemented", curated[0]["output"])

    def test_never_mutates_source_list(self) -> None:
        samples = [
            {
                "instruction": "Do task A",
                "input": "",
                "output": "Valid output sample",
                "source": "feedback",
                "category": "feedback",
                "rating": "5",
            }
        ]
        before = len(samples)
        curated, _ = curate_samples(samples)
        self.assertEqual(len(samples), before)
        self.assertEqual(len(curated), 1)


if __name__ == "__main__":
    unittest.main()
