"""Tests for teacher distillation service."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.teacher_distillation_service import TeacherDistillationService


class TeacherDistillationServiceTests(unittest.TestCase):
    def test_distill_samples_offline_caller(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = TeacherDistillationService(
                teacher_model="ollama:deepseek-coder",
                cloud_teacher_model="openai_compat:deepseek-ai/DeepSeek-V3",
                datasets_dir=tmp,
                llm_caller=lambda _model, _prompt: "ideal answer with patch and verify",
                max_samples=10,
            )
            samples = [
                {
                    "instruction": "fix failing test in app/main.py",
                    "input": "[run_started] ok",
                    "category": "coding",
                }
            ]
            result = service.distill_samples(samples, name="test-distill")
            self.assertEqual(result.sample_count, 1)
            self.assertTrue(Path(result.dataset_path).exists())
            self.assertIn("DeepSeek-V3", result.teacher_model)


if __name__ == "__main__":
    unittest.main()
