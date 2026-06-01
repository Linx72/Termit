from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.finetune_trainer_service import FinetuneTrainerService


class FinetuneDpoTrainerTests(unittest.TestCase):
    def test_hf_dpo_mode_prepares_dpo_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "pairs_dpo.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "instruction": "Fix verify resolver",
                        "chosen": "Use resolve_verify_command from repo root.",
                        "rejected": "Run pytest without changing cwd.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            trainer = FinetuneTrainerService(
                modelfiles_dir=tmp,
                adapters_dir=str(Path(tmp) / "adapters"),
                trainer_mode="hf",
                hf_dry_run=True,
            )
            result = trainer.train_dataset(
                dataset_path=str(dataset),
                base_model="ollama:deepseek-coder",
                output_model="termit-ft",
                training_mode="dpo",
                job_id="dpo-dry-run",
            )
            self.assertEqual(result.status, "completed")
            self.assertIn("dpo_train.py", result.command or "")
            self.assertIn("DPO dry-run", result.detail)


if __name__ == "__main__":
    unittest.main()
