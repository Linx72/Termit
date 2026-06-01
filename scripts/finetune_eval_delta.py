#!/usr/bin/env python3
"""Baseline eval → optional train → post-eval → delta report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.finetune_regression_gate import evaluate_training_regression


def api_request(
    *,
    method: str,
    base_url: str,
    path: str,
    api_key: Optional[str],
    body: Optional[dict[str, object]] = None,
    timeout: float = 600.0,
) -> dict[str, object]:
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=True).encode("utf-8")
    request = Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def run_eval_suite(base_url: str, api_key: Optional[str], *, limit: Optional[int]) -> dict[str, object]:
    body: dict[str, object] = {}
    if limit is not None:
        body["limit"] = limit
    return api_request(
        method="POST",
        base_url=base_url,
        path="/api/eval/run-suite",
        api_key=api_key,
        body=body,
        timeout=1800.0,
    )


def append_delta_report(report_path: Path, row: dict[str, object]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Finetune eval delta: baseline → train → post-eval")
    parser.add_argument("--base-url", default=os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--api-key", default=os.getenv("TERMIT_API_KEY"))
    parser.add_argument("--eval-limit", type=int, default=int(os.getenv("TERMIT_STAGE1_EVAL_LIMIT", "0")))
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-post-eval", action="store_true")
    parser.add_argument(
        "--report-file",
        default=os.getenv("TERMIT_EVAL_REPORT_FILE", str(ROOT / "data" / "eval_reports.jsonl")),
    )
    parser.add_argument(
        "--max-regression",
        type=float,
        default=float(os.getenv("TERMIT_FINETUNE_MAX_TRAIN_REGRESSION", "0.02")),
    )
    parser.add_argument(
        "--block-regression",
        action="store_true",
        default=os.getenv("TERMIT_EVAL_BLOCK_REGRESSION", "false").lower() == "true",
    )
    args = parser.parse_args()

    eval_limit = args.eval_limit if args.eval_limit > 0 else None
    baseline: Optional[dict[str, object]] = None
    if not args.skip_baseline:
        print("[finetune_eval_delta] baseline eval...")
        baseline = run_eval_suite(args.base_url, args.api_key, limit=eval_limit)
        print(
            f"[finetune_eval_delta] baseline pass_rate={baseline.get('pass_rate')} "
            f"total={baseline.get('total')}"
        )

    if not args.skip_train:
        print("[finetune_eval_delta] continuous learning train...")
        script = ROOT / "scripts" / "finetune_continuous_learning.sh"
        env = os.environ.copy()
        env.setdefault("TERMIT_FINETUNE_RUN_STAGE1", "false")
        completed = subprocess.run(["bash", str(script)], cwd=str(ROOT), env=env, check=False)
        if completed.returncode != 0:
            print("[finetune_eval_delta] train step failed (non-fatal for eval-only runs)", file=sys.stderr)

    post: Optional[dict[str, object]] = None
    if not args.skip_post_eval:
        print("[finetune_eval_delta] post-train eval...")
        post = run_eval_suite(args.base_url, args.api_key, limit=eval_limit)
        print(
            f"[finetune_eval_delta] post pass_rate={post.get('pass_rate')} total={post.get('total')}"
        )

    baseline_rate = float(baseline["pass_rate"]) if baseline and "pass_rate" in baseline else None
    post_rate = float(post["pass_rate"]) if post and "pass_rate" in post else None
    delta = (post_rate - baseline_rate) if baseline_rate is not None and post_rate is not None else None

    decision = evaluate_training_regression(
        baseline_pass_rate=baseline_rate,
        post_pass_rate=post_rate,
        max_regression=args.max_regression,
        shadow_on_regression=True,
        require_post_eval=not args.skip_post_eval,
    )

    report_row = {
        "kind": "finetune_eval_delta",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline_pass_rate": baseline_rate,
        "post_pass_rate": post_rate,
        "delta": delta,
        "regression": decision.as_dict(),
        "baseline_total": baseline.get("total") if baseline else None,
        "post_total": post.get("total") if post else None,
    }
    append_delta_report(Path(args.report_file), report_row)
    print(json.dumps(report_row, indent=2, ensure_ascii=False))

    if args.block_regression and not decision.promote:
        print(f"[finetune_eval_delta] regression blocked: {decision.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"[finetune_eval_delta] API error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
