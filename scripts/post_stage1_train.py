#!/usr/bin/env python3
"""Wait for Stage1 run completion, train model, optional post-eval."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def _load_kpi_gate():
    path = ROOT / "scripts" / "finetune_eval_kpi_gate.py"
    spec = importlib.util.spec_from_file_location("finetune_eval_kpi_gate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def api_request(
    *,
    method: str,
    base_url: str,
    path: str,
    api_key: Optional[str],
    body: Optional[dict[str, object]] = None,
    timeout: float = 60.0,
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


def wait_for_run(
    *,
    base_url: str,
    api_key: Optional[str],
    run_id: str,
    poll_seconds: float,
    timeout_seconds: float,
) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        run = api_request(
            method="GET",
            base_url=base_url,
            path=f"/api/finetune/pipeline/stage1-runs/{run_id}",
            api_key=api_key,
        )
        status = str(run.get("status", ""))
        if status in {"completed", "failed", "cancelled"}:
            return run
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for run {run_id}")


def resolve_latest_completed(base_url: str, api_key: Optional[str]) -> str:
    payload = api_request(
        method="GET",
        base_url=base_url,
        path="/api/finetune/pipeline/stage1-runs?limit=20&status=completed",
        api_key=api_key,
    )
    runs = payload.get("runs") or []
    if not runs:
        raise RuntimeError("No completed Stage1 runs found.")
    return str(runs[0]["run_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-Stage1 train + optional eval")
    parser.add_argument("run_id", nargs="?", default=None, help="Stage1 run id (ftpbg_...)")
    parser.add_argument("--latest-completed", action="store_true")
    parser.add_argument("--base-url", default=os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--api-key", default=os.getenv("TERMIT_API_KEY"))
    parser.add_argument("--output-model", default=os.getenv("TERMIT_FINETUNE_OUTPUT_MODEL"))
    parser.add_argument("--trainer-mode", default=os.getenv("TERMIT_FINETUNE_TRAINER"))
    parser.add_argument("--auto-register-adapter", action="store_true")
    parser.add_argument("--repo-profile-id", default=os.getenv("TERMIT_FINETUNE_REPO_PROFILE_ID"))
    parser.add_argument("--wait", action="store_true", help="Poll until run completes")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--run-post-eval", action="store_true")
    parser.add_argument("--eval-limit", type=int, default=int(os.getenv("TERMIT_STAGE1_EVAL_LIMIT", "24")))
    args = parser.parse_args()

    run_id = args.run_id
    if args.latest_completed:
        run_id = resolve_latest_completed(args.base_url, args.api_key)
    if not run_id:
        print("run_id required (or use --latest-completed)", file=sys.stderr)
        return 1

    try:
        if args.wait:
            run = wait_for_run(
                base_url=args.base_url,
                api_key=args.api_key,
                run_id=run_id,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            )
            if str(run.get("status")) != "completed":
                print(json.dumps(run, indent=2, ensure_ascii=True))
                return 1

        train_body: dict[str, object] = {"auto_register_adapter": args.auto_register_adapter}
        if args.output_model:
            train_body["output_model"] = args.output_model
        if args.trainer_mode:
            train_body["trainer_mode"] = args.trainer_mode
        if args.repo_profile_id:
            train_body["repo_profile_id"] = args.repo_profile_id

        train_result = api_request(
            method="POST",
            base_url=args.base_url,
            path=f"/api/finetune/pipeline/stage1-runs/{run_id}/train",
            api_key=args.api_key,
            body=train_body,
            timeout=max(args.timeout_seconds, 120.0),
        )
        print(json.dumps(train_result, indent=2, ensure_ascii=True))

        eval_result: dict[str, object] | None = None
        if args.run_post_eval and str(train_result.get("status")) == "completed":
            eval_result = api_request(
                method="POST",
                base_url=args.base_url,
                path="/api/eval/run-suite",
                api_key=args.api_key,
                body={"limit": args.eval_limit, "persist_report": True},
                timeout=max(args.timeout_seconds, 120.0),
            )
            print(json.dumps(eval_result, indent=2, ensure_ascii=True))

            reports_dir = ROOT / "data" / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            eval_path = reports_dir / f"stage1_post_eval_{run_id}.json"
            eval_path.write_text(json.dumps(eval_result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            baseline_path = Path(os.getenv("TERMIT_EVAL_BASELINE", str(ROOT / "data" / "eval_baseline_release.json")))
            min_improve = float(os.getenv("TERMIT_FINETUNE_MIN_EVAL_IMPROVEMENT", "0.05"))
            kpi_mod = _load_kpi_gate()
            baseline_rate = kpi_mod.load_baseline_rate(baseline_path)
            current_rate = kpi_mod._pass_rate_from_report(eval_result)
            kpi_summary = kpi_mod.evaluate_improvement_kpi(
                baseline_pass_rate=baseline_rate,
                current_pass_rate=current_rate,
                min_improvement=min_improve,
            )
            print(json.dumps({"eval_kpi": kpi_summary}, indent=2, ensure_ascii=True))

            if os.getenv("TERMIT_EVAL_AUTO_PROMOTE_BASELINE", "false").lower() == "true" and baseline_path.is_file():
                promote_path = ROOT / "scripts" / "eval_baseline_promote.py"
                promote_spec = importlib.util.spec_from_file_location("eval_baseline_promote", promote_path)
                if promote_spec and promote_spec.loader:
                    promote_mod = importlib.util.module_from_spec(promote_spec)
                    promote_spec.loader.exec_module(promote_mod)
                    max_drop = float(os.getenv("TERMIT_EVAL_MAX_PASS_RATE_DROP", "0.05"))
                    min_promote = float(os.getenv("TERMIT_EVAL_MIN_IMPROVEMENT_FOR_PROMOTE", str(min_improve)))
                    _, promote_summary = promote_mod.promote_baseline(
                        baseline_path=baseline_path,
                        current_path=eval_path,
                        max_pass_rate_drop=max_drop,
                        min_improvement=min_promote,
                        dry_run=False,
                    )
                    print(json.dumps({"baseline_promote": promote_summary}, indent=2, ensure_ascii=False))

            if os.getenv("TERMIT_FINETUNE_KPI_STRICT", "false").lower() == "true" and not kpi_summary.get("kpi_passed"):
                return 3
    except HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except (URLError, TimeoutError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0 if str(train_result.get("status")) == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
