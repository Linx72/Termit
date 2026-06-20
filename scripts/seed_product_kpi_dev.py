#!/usr/bin/env python3
"""Локальный dev-seed для Product KPI gates (tool-loop window, chat p95, local share)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.domain.schemas import AgentRunEvent, AgentRunRecordResponse, AgentRunState
from app.services.desktop_workflow_telemetry_service import DesktopWorkflowTelemetryService
from app.services.sqlite_agent_run_store import SQLiteAgentRunStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_tool_loop_runs(store: SQLiteAgentRunStore, runs: int) -> int:
    created = 0
    for index in range(runs):
        run_id = f"arun_kpi_seed_{index:02d}"
        ts = _utc_now()
        store.put_run(
            AgentRunRecordResponse(
                run_id=run_id,
                agent_id="agt_kpi_seed",
                agent_name="KPI Dev Seed",
                state=AgentRunState.completed,
                created_at=ts,
                updated_at=ts,
                input=f"kpi seed run {index}",
                session_id=f"sess_kpi_{index}",
                provider="ollama",
                model="ollama:termit-core-ft",
                attempts=1,
                max_attempts=3,
                response="ok",
            )
        )
        store.append_event(
            run_id,
            AgentRunEvent(
                event_type="mcp_context_injected",
                state=AgentRunState.running,
                message="dev seed mcp",
                timestamp=ts,
                attempt=1,
            ),
        )
        store.append_event(
            run_id,
            AgentRunEvent(
                event_type="tool_loop_tool",
                state=AgentRunState.running,
                message="list_files",
                timestamp=ts,
                attempt=1,
            ),
        )
        store.append_event(
            run_id,
            AgentRunEvent(
                event_type="tool_loop_final",
                state=AgentRunState.completed,
                message="final",
                timestamp=ts,
                attempt=1,
            ),
        )
        created += 1
    return created


def seed_workflow_local_runs(state_dir: str, count: int) -> int:
    telemetry = DesktopWorkflowTelemetryService(state_dir)
    for index in range(count):
        telemetry.record(
            event_type="agent_run_created",
            journey_id="kpi-dev",
            execution_mode="local",
            ok=True,
            detail=f"seed local run {index}",
        )
    return count


def seed_chat_metrics_file(state_dir: str, samples: int = 55, latency_ms: int = 800) -> Path:
    """Персистентный dev-seed chat p95 (читается TelemetryStore при cold start)."""
    latencies = [latency_ms + (index % 5) * 20 for index in range(max(5, samples))]
    payload = {
        "dev_only": True,
        "chat_latencies_ms": latencies,
        "chat_requests_total": len(latencies),
        "chat_success_total": len(latencies),
        "chat_cache_miss_total": len(latencies),
        "task_total": 20,
        "task_completed": 16,
        "task_failed": 4,
        "task_auto_total": 14,
    }
    path = Path(state_dir).resolve() / "dev_chat_metrics_seed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def warm_and_chat(base_url: str, chats: int, timeout: int) -> int:
    try:
        urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=5)
    except (urllib.error.URLError, TimeoutError):
        return 0
    try:
        warm_req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/local/models/warm",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(warm_req, timeout=120)
    except (urllib.error.URLError, TimeoutError):
        pass
    ok = 0
    payload = json.dumps(
        {
            "message": "ping",
            "task_type": "general",
            "model": "ollama:qwen2.5-coder",
            "use_retrieval": False,
            "use_repo_map": False,
        }
    ).encode("utf-8")
    for _ in range(chats):
        try:
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    ok += 1
        except (urllib.error.URLError, TimeoutError):
            break
    return ok


def post_reload_dev_metrics(base_url: str) -> dict[str, object] | None:
    try:
        urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=5)
    except (urllib.error.URLError, TimeoutError):
        return None
    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/ops/reload-dev-metrics-seed",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed local Product KPI metrics (dev only)")
    parser.add_argument("--runs", type=int, default=6, help="Успешных tool-loop run'ов (≥5)")
    parser.add_argument("--local-runs", type=int, default=120, help="Workflow local agent_run_created")
    parser.add_argument("--chats", type=int, default=12, help="Chat запросы к API (0 = пропуск)")
    parser.add_argument("--chat-timeout", type=int, default=90, help="Таймаут одного chat запроса (сек)")
    parser.add_argument("--base-url", default=os.getenv("TERMIT_BASE_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.force and os.getenv("TERMIT_PRODUCT_KPI_DEV_SEED", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        print(
            "Отказ: TERMIT_PRODUCT_KPI_DEV_SEED=true или --force (только local dev).",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    tool_runs = 0
    if args.runs > 0:
        store = SQLiteAgentRunStore(db_path=settings.agent_run_sqlite_path)
        tool_runs = seed_tool_loop_runs(store, max(5, args.runs))
    local_rows = 0
    if args.local_runs > 0:
        local_rows = seed_workflow_local_runs(settings.desktop_state_dir, max(5, args.local_runs))
    chat_seed_path = seed_chat_metrics_file(settings.desktop_state_dir)
    chats_ok = 0
    if args.chats > 0:
        chats_ok = warm_and_chat(
            args.base_url,
            max(1, args.chats),
            timeout=max(10, args.chat_timeout),
        )

    from app.state import (
        _build_agent_service,
        _build_desktop_kpi_gate_service,
        _build_telemetry_store,
    )

    _build_telemetry_store.cache_clear()

    reload_payload = post_reload_dev_metrics(args.base_url)

    agent_metrics = _build_agent_service().queue_metrics()
    kpi = _build_desktop_kpi_gate_service().evaluate_gates()
    summary = {
        "tool_loop_runs_seeded": tool_runs,
        "workflow_local_seeded": local_rows,
        "chat_requests_ok": chats_ok,
        "chat_metrics_seed_file": str(chat_seed_path),
        "live_reload": reload_payload,
        "tool_loop_window": {
            "runs": agent_metrics.get("tool_loop_runs_recent_window"),
            "completion": agent_metrics.get("tool_loop_completion_rate_recent_window"),
            "success": agent_metrics.get("tool_loop_tool_success_rate_recent_window"),
        },
        "kpi_passed_count": kpi.get("passed_count"),
        "kpi_total_gates": kpi.get("total_gates"),
        "kpi_overall_passed": kpi.get("overall_passed"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(
        f"OK — seeded tool-loop={tool_runs}, workflow_local={local_rows}, chats_ok={chats_ok}"
    )
    if reload_payload and reload_payload.get("reloaded"):
        print(f"Live API telemetry reloaded (chat_total={reload_payload.get('chat_requests_total')})")
    else:
        print(f"Chat metrics seed: {chat_seed_path} (POST /api/ops/reload-dev-metrics-seed или restart API)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
