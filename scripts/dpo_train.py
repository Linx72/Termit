#!/usr/bin/env python3
"""Termit DPO trainer — TRL DPOTrainer via Unsloth (GPU) or dry-run manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_rows(dataset_path: Path, max_samples: int) -> list[dict]:
    rows: list[dict] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
        if len(rows) >= max_samples:
            break
    return rows


def _row_to_prompt(row: dict) -> str:
    instruction = str(row.get("instruction", "")).strip()
    inp = str(row.get("input", "")).strip()
    if inp:
        return f"{instruction}\n\n{inp}".strip()
    return instruction


def main() -> int:
    parser = argparse.ArgumentParser(description="Termit DPO trainer")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--max-samples", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(dataset_path, max(1, args.max_samples))
    pairs = [
        row
        for row in rows
        if str(row.get("chosen", "")).strip() and str(row.get("rejected", "")).strip()
    ]
    if not pairs:
        print(f"No DPO pairs (chosen/rejected) in {dataset_path}", file=sys.stderr)
        return 1

    manifest = {
        "base_model": args.base_model,
        "dataset": str(dataset_path),
        "pairs": len(pairs),
        "output_dir": str(output_dir),
        "epochs": args.epochs,
        "lora_rank": args.lora_rank,
        "training_mode": "dpo",
    }

    if args.dry_run:
        (output_dir / "termit_dpo_manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({**manifest, "status": "dry_run"}))
        return 0

    try:
        from unsloth import FastLanguageModel  # type: ignore[import-untyped]
        import torch  # type: ignore[import-untyped]
        from trl import DPOTrainer  # type: ignore[import-untyped]
        from transformers import TrainingArguments  # type: ignore[import-untyped]
        from datasets import Dataset  # type: ignore[import-untyped]
    except ImportError as exc:
        print(
            "Unsloth DPO stack not installed. Run: pip install unsloth trl datasets transformers",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 2

    prompts = [_row_to_prompt(row) for row in pairs]
    chosen = [str(row.get("chosen", "")).strip() for row in pairs]
    rejected = [str(row.get("rejected", "")).strip() for row in pairs]

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

    dataset = Dataset.from_dict({"prompt": prompts, "chosen": chosen, "rejected": rejected})
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=max(1, args.epochs),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            learning_rate=5e-5,
            logging_steps=5,
            save_strategy="epoch",
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            report_to=[],
        ),
        train_dataset=dataset,
        tokenizer=tokenizer,
    )
    trainer.train()
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    manifest["status"] = "completed"
    (output_dir / "termit_dpo_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
