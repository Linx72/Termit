import json
import tempfile
import unittest
from pathlib import Path

from app.services.finetune_adapter_resolver import FinetuneAdapterResolver
from app.services.finetune_gguf_converter import convert_adapter_to_gguf
from app.services.training_signal_store import TrainingSignalStore


class FinetuneAdapterResolverTests(unittest.TestCase):
    def test_resolve_latest_adapter_for_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adapters.json"
            path.write_text(
                json.dumps(
                    {
                        "adapters": [
                            {
                                "adapter_id": "a1",
                                "repo_profile_id": "termit-core",
                                "model": "ollama:termit-ft-v1",
                                "registered_at": "2026-06-01T00:00:00Z",
                            },
                            {
                                "adapter_id": "a2",
                                "repo_profile_id": "termit-core",
                                "model": "ollama:termit-ft-v2",
                                "registered_at": "2026-06-02T00:00:00Z",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            resolver = FinetuneAdapterResolver(str(path))
            self.assertEqual(resolver.resolve_model("termit-core"), "ollama:termit-ft-v2")


class FinetuneGgufConverterTests(unittest.TestCase):
    def test_skips_when_no_peft_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter_dir = Path(tmp) / "adapter"
            adapter_dir.mkdir()
            out = Path(tmp) / "out.gguf"
            result = convert_adapter_to_gguf(
                adapter_dir=adapter_dir,
                output_gguf=out,
                base_model="meta-llama/Llama-3.2-3B",
            )
            self.assertEqual(result.status, "skipped")


class TrainingSignalDpoTests(unittest.TestCase):
    def test_load_dpo_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TrainingSignalStore(str(Path(tmp) / "signals.jsonl"), min_output_chars=8)
            store.try_capture_negative_tool_step(
                run_id="r1",
                step=1,
                action="tool",
                tool="apply_patch",
                observation='{"verify":{"executed":true,"exit_code":1}}',
                instruction="Fix failing test",
                reason="verify_failed",
            )
            rows = store.load_dpo_samples(limit=10)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source"], "dpo_negative")


if __name__ == "__main__":
    unittest.main()
