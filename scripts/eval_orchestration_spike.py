#!/usr/bin/env python3
"""Run a focused eval slice for the mini-style orchestration loop."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PROMPTS = [
    "Refactor a utility module and document changed files.",
    "Fix flaky test behavior and explain verification steps.",
    "Add small feature flag and include rollback note.",
    "Harden error handling path and provide test update plan.",
    "Prepare release notes summary with touched areas.",
]


def _load_prompts_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    prompts: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                prompt = str(item.get("prompt", "")).strip()
                if prompt:
                    prompts.append(prompt)
            elif isinstance(item, str) and item.strip():
                prompts.append(item.strip())
    return prompts


def _post_json(url: str, payload: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _delta(after: dict[str, Any], before: dict[str, Any], key: str) -> float:
    return float(after.get(key, 0.0)) - float(before.get(key, 0.0))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        Path(tmp_path).replace(path)
    finally:
        if Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run mini-style orchestration eval slice")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--prompt", action="append", dest="prompts")
    parser.add_argument(
        "--prompts-file",
        default="data/eval_scenarios_orchestration.json",
        help="JSON array of prompts or scenario objects with `prompt` field",
    )
    parser.add_argument("--max-prompts", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    parser.add_argument(
        "--output-file",
        default="",
        help="Optional path to save JSON report atomically",
    )
    parser.add_argument(
        "--append-report-file",
        default="",
        help="Optional JSONL file path to append report snapshots",
    )
    args = parser.parse_args()

    file_prompts = _load_prompts_from_file(Path(args.prompts_file))
    prompts = args.prompts or file_prompts or list(DEFAULT_PROMPTS)
    max_prompts = max(1, args.max_prompts)
    prompts = prompts[:max_prompts]
    timeout_seconds = max(10, args.timeout_seconds)
    metrics_before = _get_json(
        f"{args.base_url}/api/orchestration/metrics",
        timeout_seconds=timeout_seconds,
    )
    results: list[dict[str, Any]] = []

    for prompt in prompts:
        try:
            payload = {
                "input": prompt,
                "task_type": "coding",
                "use_retrieval": False,
            }
            result = _post_json(
                f"{args.base_url}/api/orchestration/run",
                payload,
                timeout_seconds=timeout_seconds,
            )
            results.append(
                {
                    "prompt": prompt,
                    "status": result.get("status"),
                    "run_id": result.get("run_id"),
                    "phase_count": len(result.get("phases", [])),
                    "action_observation_count": len(result.get("action_observation", []) or []),
                }
            )
        except (urllib.error.HTTPError, TimeoutError) as exc:
            results.append(
                {
                    "prompt": prompt,
                    "status": "failed",
                    "error": f"http_{exc.code}" if isinstance(exc, urllib.error.HTTPError) else "timeout",
                }
            )

    metrics_after = _get_json(
        f"{args.base_url}/api/orchestration/metrics",
        timeout_seconds=timeout_seconds,
    )
    passed = sum(1 for item in results if item.get("status") == "completed")
    report = {
        "total": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "results": results,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "delta": {
            "orchestration_runs_total": _delta(
                metrics_after,
                metrics_before,
                "orchestration_runs_total",
            ),
            "coder_retry_runs_total": _delta(
                metrics_after,
                metrics_before,
                "coder_retry_runs_total",
            ),
            "coder_retry_success_runs_total": _delta(
                metrics_after,
                metrics_before,
                "coder_retry_success_runs_total",
            ),
            "reviewer_reject_total": _delta(metrics_after, metrics_before, "reviewer_reject_total"),
            "avg_coder_attempts_after": float(metrics_after.get("avg_coder_attempts", 0.0)),
            "coder_retry_success_rate_after": float(
                metrics_after.get("coder_retry_success_rate", 0.0)
            ),
        },
    }
    print(json.dumps(report, indent=2))
    if args.output_file:
        _write_json_atomic(Path(args.output_file), report)
    if args.append_report_file:
        report_with_ts = {"timestamp": datetime.now(timezone.utc).isoformat(), **report}
        _append_jsonl(Path(args.append_report_file), report_with_ts)
    min_pass_rate = min(1.0, max(0.0, float(args.min_pass_rate)))
    return 0 if report["pass_rate"] + 1e-9 >= min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
