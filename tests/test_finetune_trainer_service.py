import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.finetune_trainer_service import FinetuneTrainerService


class FinetuneTrainerServiceTests(unittest.TestCase):
    def test_build_modelfile_includes_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "data.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "instruction": "Explain health endpoint",
                        "input": "",
                        "output": "GET /health returns ok status.",
                        "source": "task",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            trainer = FinetuneTrainerService(modelfiles_dir=tmp, trainer_mode="modelfile")
            body = trainer.build_modelfile(base_model="ollama:deepseek-coder", dataset_path=dataset)
            self.assertIn("FROM deepseek-coder", body)
            self.assertIn("Explain health endpoint", body)

    def test_modelfile_mode_skips_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "data.jsonl"
            dataset.write_text(
                json.dumps({"instruction": "x", "output": "y", "source": "feedback"}) + "\n",
                encoding="utf-8",
            )
            trainer = FinetuneTrainerService(modelfiles_dir=tmp, trainer_mode="modelfile")
            result = trainer.train_dataset(
                dataset_path=str(dataset),
                base_model="ollama:deepseek-coder",
                output_model="termit-ft",
            )
            self.assertEqual(result.status, "completed")
            self.assertTrue(Path(result.modelfile_path or "").exists())

    @patch("app.services.finetune_trainer_service.subprocess.run")
    @patch("app.services.finetune_trainer_service.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_mode_runs_create(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="created", stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "data.jsonl"
            dataset.write_text(
                json.dumps({"instruction": "x", "output": "y", "source": "feedback"}) + "\n",
                encoding="utf-8",
            )
            trainer = FinetuneTrainerService(modelfiles_dir=tmp, trainer_mode="ollama")
            result = trainer.train_dataset(
                dataset_path=str(dataset),
                base_model="ollama:deepseek-coder",
                output_model="termit-ft",
            )
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output_model, "termit-ft")
            mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
