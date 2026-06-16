#!/usr/bin/env python3
"""Minimal Unsloth DPO trainer for Termit preference datasets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_rows(dataset_path: Path, max_samples: int) -> list[dict]:
    rows: list[dict] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        rows.append(item)
        if len(rows) >= max_samples:
            break
    return rows


def _row_to_prompt(row: dict) -> str:
    instruction = str(row.get("instruction", "")).strip()
    inp = str(row.get("input", "")).strip()
    return f"{instruction}\n\n{inp}".strip() if inp else instruction


def main() -> int:
    parser = argparse.ArgumentParser(description="Termit Unsloth DPO trainer")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--max-samples", type=int, default=500)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(dataset_path, max(1, args.max_samples))
    prepared = []
    for row in rows:
        prompt = _row_to_prompt(row)
        chosen = str(row.get("chosen", "")).strip()
        rejected = str(row.get("rejected", "")).strip()
        if not prompt or not chosen or not rejected or chosen == rejected:
            continue
        prepared.append({"prompt": prompt, "chosen": chosen, "rejected": rejected})
    if not prepared:
        print(f"No valid DPO rows in {dataset_path}", file=sys.stderr)
        return 1

    try:
        from unsloth import FastLanguageModel  # type: ignore[import-untyped]
        import torch  # type: ignore[import-untyped]
        from datasets import Dataset  # type: ignore[import-untyped]
        from trl import DPOConfig, DPOTrainer  # type: ignore[import-untyped]
    except ImportError as exc:
        print(
            "Unsloth DPO stack not installed. Run: pip install unsloth trl datasets transformers",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 2

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=4096,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=max(4, args.lora_rank),
        lora_alpha=max(8, args.lora_rank * 2),
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
    )
    dataset = Dataset.from_list(prepared)
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=DPOConfig(
            output_dir=str(output_dir),
            num_train_epochs=max(1, args.epochs),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            learning_rate=1e-5,
            logging_steps=5,
            save_strategy="epoch",
            report_to=[],
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
        ),
        train_dataset=dataset,
        processing_class=tokenizer,
    )
    trainer.train()
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    manifest = {
        "mode": "dpo",
        "base_model": args.base_model,
        "dataset": str(dataset_path),
        "samples": len(prepared),
        "output_dir": str(output_dir),
        "epochs": args.epochs,
        "lora_rank": args.lora_rank,
    }
    (output_dir / "termit_dpo_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
