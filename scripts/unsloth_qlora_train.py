#!/usr/bin/env python3
"""Termit Unsloth QLoRA trainer — generated script; requires GPU + unsloth."""
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


def _row_to_text(row: dict) -> str:
    messages = row.get("messages")
    if isinstance(messages, list) and messages:
        parts: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role", "user"))
            content = str(message.get("content", "")).strip()
            if content:
                parts.append(f"### {role}:\n{content}")
        return "\n\n".join(parts).strip()
    instruction = str(row.get("instruction", "")).strip()
    inp = str(row.get("input", "")).strip()
    output = str(row.get("output", "")).strip()
    prompt = instruction
    if inp:
        prompt = f"{instruction}\n\n{inp}".strip()
    return f"### user:\n{prompt}\n\n### assistant:\n{output}".strip()


def _row_to_dpo_text(row: dict) -> tuple[str, str, str] | None:
    instruction = str(row.get("instruction", "")).strip()
    inp = str(row.get("input", "")).strip()
    chosen = str(row.get("chosen", "")).strip()
    rejected = str(row.get("rejected", "")).strip()
    if not chosen or not rejected:
        return None
    prompt = instruction
    if inp:
        prompt = f"{instruction}\n\n{inp}".strip()
    return prompt, chosen, rejected


def _train_sft(args, rows: list[dict], output_dir: Path, dataset_path: Path) -> int:
    try:
        from unsloth import FastLanguageModel  # type: ignore[import-untyped]
        import torch  # type: ignore[import-untyped]
        from trl import SFTTrainer  # type: ignore[import-untyped]
        from transformers import TrainingArguments  # type: ignore[import-untyped]
        from datasets import Dataset  # type: ignore[import-untyped]
    except ImportError as exc:
        print(
            "Unsloth stack not installed. Run: pip install unsloth trl datasets transformers",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 2

    texts = [_row_to_text(row) for row in rows if _row_to_text(row)]
    if not texts:
        print("No convertible training texts.", file=sys.stderr)
        return 1

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

    train_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=max(1, args.epochs),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=5,
        save_strategy="epoch",
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        report_to=[],
    )

    dataset = Dataset.from_dict({"text": texts})
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=4096,
        args=train_args,
    )
    trainer.train()
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    manifest = {
        "training_mode": "sft",
        "base_model": args.base_model,
        "dataset": str(dataset_path),
        "samples": len(texts),
        "output_dir": str(output_dir),
        "epochs": args.epochs,
        "lora_rank": args.lora_rank,
    }
    (output_dir / "termit_train_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest))
    return 0


def _train_dpo(args, rows: list[dict], output_dir: Path, dataset_path: Path) -> int:
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

    prompts: list[str] = []
    chosen: list[str] = []
    rejected: list[str] = []
    for row in rows:
        parsed = _row_to_dpo_text(row)
        if parsed is None:
            continue
        prompt, good, bad = parsed
        prompts.append(prompt)
        chosen.append(good)
        rejected.append(bad)
    if not prompts:
        print("No DPO pairs in dataset.", file=sys.stderr)
        return 1

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

    manifest = {
        "training_mode": "dpo",
        "base_model": args.base_model,
        "dataset": str(dataset_path),
        "samples": len(prompts),
        "output_dir": str(output_dir),
        "epochs": args.epochs,
        "lora_rank": args.lora_rank,
    }
    (output_dir / "termit_train_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Termit Unsloth QLoRA trainer")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--max-samples", type=int, default=500)
    parser.add_argument("--training-mode", choices=("sft", "dpo"), default="sft")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(dataset_path, max(1, args.max_samples))
    if not rows:
        print(f"No training rows in {dataset_path}", file=sys.stderr)
        return 1

    if args.training_mode == "dpo":
        return _train_dpo(args, rows, output_dir, dataset_path)
    return _train_sft(args, rows, output_dir, dataset_path)


if __name__ == "__main__":
    raise SystemExit(main())
