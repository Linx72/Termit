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

    def test_hf_mode_prepares_unsloth_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "data.jsonl"
            dataset.write_text(
                json.dumps({"instruction": "x", "output": "y enough chars", "source": "feedback"}) + "\n",
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
                job_id="hf-dry-run",
            )
            self.assertEqual(result.status, "completed")
            self.assertTrue(result.command)
            self.assertIn("unsloth_qlora_train.py", result.command or "")
            self.assertIn("dry-run", result.detail.lower())

    def test_build_modelfile_includes_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapters = Path(tmp) / "adapters" / "termit-core"
            adapters.mkdir(parents=True)
            gguf = adapters / "termit-ft.gguf"
            gguf.write_text("fake", encoding="utf-8")
            dataset = Path(tmp) / "data.jsonl"
            dataset.write_text(
                json.dumps({"instruction": "x", "output": "y", "source": "feedback"}) + "\n",
                encoding="utf-8",
            )
            trainer = FinetuneTrainerService(
                modelfiles_dir=tmp,
                adapters_dir=str(Path(tmp) / "adapters"),
                trainer_mode="modelfile",
            )
            body = trainer.build_modelfile(
                base_model="ollama:deepseek-coder",
                dataset_path=dataset,
                adapter_gguf=gguf,
            )
            self.assertIn("ADAPTER", body)
            self.assertIn("termit-ft.gguf", body)

    @patch("app.services.finetune_trainer_service.subprocess.run")
    @patch("app.services.finetune_trainer_service.FinetuneTrainerService._probe_ollama", side_effect=[False, True])
    @patch("app.services.finetune_trainer_service.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_mode_auto_starts_server(
        self,
        _which: MagicMock,
        _probe: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="created", stderr=""),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "data.jsonl"
            dataset.write_text(
                json.dumps({"instruction": "x", "output": "y", "source": "feedback"}) + "\n",
                encoding="utf-8",
            )
            trainer = FinetuneTrainerService(
                modelfiles_dir=tmp,
                trainer_mode="ollama",
                ollama_host="127.0.0.1:11434",
            )
            result = trainer.train_dataset(
                dataset_path=str(dataset),
                base_model="ollama:deepseek-coder",
                output_model="termit-ft",
            )
            self.assertEqual(result.status, "completed")
            self.assertGreaterEqual(mock_run.call_count, 2)

    @patch("app.services.finetune_trainer_service.FinetuneTrainerService._probe_ollama", return_value=True)
    @patch("app.services.finetune_trainer_service.subprocess.run")
    @patch("app.services.finetune_trainer_service.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_mode_runs_create(self, _which: MagicMock, mock_run: MagicMock, _probe: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="created", stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "data.jsonl"
            dataset.write_text(
                json.dumps({"instruction": "x", "output": "y", "source": "feedback"}) + "\n",
                encoding="utf-8",
            )
            trainer = FinetuneTrainerService(
                modelfiles_dir=tmp,
                trainer_mode="ollama",
                ollama_host="127.0.0.1:11434",
            )
            result = trainer.train_dataset(
                dataset_path=str(dataset),
                base_model="ollama:deepseek-coder",
                output_model="termit-ft",
            )
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output_model, "termit-ft")
            mock_run.assert_called_once()
            env = mock_run.call_args.kwargs.get("env") or {}
            self.assertEqual(env.get("OLLAMA_HOST"), "127.0.0.1:11434")


if __name__ == "__main__":
    unittest.main()
