#!/usr/bin/env python3
"""Run selected unittest suites repeatedly and emit flaky-watch report."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IterationResult:
    suite: str
    iteration: int
    passed: bool
    duration_seconds: float
    returncode: int
    output_tail: str


def _tail(text: str, *, max_lines: int = 12) -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-max_lines:])


def run_iteration(*, suite: str, iteration: int, python_bin: str) -> IterationResult:
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603
        [python_bin, "-m", "unittest", suite, "-q"],  # noqa: S607
        text=True,
        capture_output=True,
        check=False,
    )
    duration = time.monotonic() - started
    merged = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return IterationResult(
        suite=suite,
        iteration=iteration,
        passed=completed.returncode == 0,
        duration_seconds=round(duration, 3),
        returncode=completed.returncode,
        output_tail=_tail(merged),
    )


def build_report(results: list[IterationResult]) -> dict[str, object]:
    per_suite: dict[str, list[IterationResult]] = {}
    for item in results:
        per_suite.setdefault(item.suite, []).append(item)

    suites_payload: list[dict[str, object]] = []
    flaky_suspected = False
    for suite, items in sorted(per_suite.items()):
        pass_count = sum(1 for row in items if row.passed)
        fail_count = len(items) - pass_count
        if pass_count > 0 and fail_count > 0:
            flaky_suspected = True
        durations = [row.duration_seconds for row in items]
        suites_payload.append(
            {
                "suite": suite,
                "iterations": len(items),
                "passed": pass_count,
                "failed": fail_count,
                "pass_rate": round(pass_count / len(items), 4) if items else 0.0,
                "duration_min_seconds": round(min(durations), 3) if durations else 0.0,
                "duration_max_seconds": round(max(durations), 3) if durations else 0.0,
                "duration_mean_seconds": round(statistics.mean(durations), 3) if durations else 0.0,
                "results": [
                    {
                        "iteration": row.iteration,
                        "passed": row.passed,
                        "duration_seconds": row.duration_seconds,
                        "returncode": row.returncode,
                        "output_tail": row.output_tail,
                    }
                    for row in items
                ],
            }
        )
    total = len(results)
    passed_total = sum(1 for row in results if row.passed)
    failed_total = total - passed_total
    return {
        "total_iterations": total,
        "passed_iterations": passed_total,
        "failed_iterations": failed_total,
        "pass_rate": round(passed_total / total, 4) if total else 0.0,
        "flaky_suspected": flaky_suspected,
        "suites": suites_payload,
    }


def _to_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Nightly Flaky Watch",
        "",
        f"- total_iterations: {report.get('total_iterations', 0)}",
        f"- passed_iterations: {report.get('passed_iterations', 0)}",
        f"- failed_iterations: {report.get('failed_iterations', 0)}",
        f"- pass_rate: {report.get('pass_rate', 0.0)}",
        f"- flaky_suspected: {report.get('flaky_suspected', False)}",
        "",
    ]
    for suite in report.get("suites", []):
        if not isinstance(suite, dict):
            continue
        lines.extend(
            [
                f"## {suite.get('suite', '')}",
                f"- iterations: {suite.get('iterations', 0)}",
                f"- passed: {suite.get('passed', 0)}",
                f"- failed: {suite.get('failed', 0)}",
                f"- pass_rate: {suite.get('pass_rate', 0.0)}",
                f"- duration_mean_seconds: {suite.get('duration_mean_seconds', 0.0)}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    default_python_bin = sys.executable
    venv_python = Path(".venv/bin/python")
    if venv_python.is_file():
        default_python_bin = str(venv_python)
    parser = argparse.ArgumentParser(description="Nightly flaky-watch report for selected unittest suites.")
    parser.add_argument(
        "--suites",
        nargs="+",
        default=["tests.test_agents_api", "tests.test_platform_e2e"],
        help="Unittest suite modules to execute.",
    )
    parser.add_argument("--iterations", type=int, default=5, help="Iterations per suite.")
    parser.add_argument("--python-bin", default=default_python_bin, help="Python interpreter to use.")
    parser.add_argument("--output", required=True, help="Output JSON report path.")
    parser.add_argument("--markdown-output", default="", help="Optional markdown summary path.")
    parser.add_argument(
        "--fail-on-failure",
        action="store_true",
        help="Exit 1 when any iteration fails.",
    )
    args = parser.parse_args()

    iterations = max(1, args.iterations)
    all_results: list[IterationResult] = []
    for suite in args.suites:
        for idx in range(1, iterations + 1):
            result = run_iteration(suite=suite, iteration=idx, python_bin=args.python_bin)
            all_results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {suite} iteration={idx} duration={result.duration_seconds}s")

    report = build_report(all_results)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Flaky-watch JSON report: {output_path}")

    if args.markdown_output:
        md_path = Path(args.markdown_output)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_to_markdown(report), encoding="utf-8")
        print(f"Flaky-watch markdown report: {md_path}")

    if args.fail_on_failure and int(report.get("failed_iterations", 0)) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
