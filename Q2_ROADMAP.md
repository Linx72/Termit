# Termit Q2 Roadmap (Impact / Effort)

## High Impact, Low Effort

- Expand eval suite automation from queued runs to full execution reports.
- Add dashboard exporter script for KPI snapshot JSON. **Done (MVP)** — `scripts/export_kpi_dashboard.py`, UI export button.
- Improve UI task panel (create/status/events in one view). **Done (MVP)** — inline task panel + events loader.

## High Impact, Medium Effort

- Role-based team workspaces (per-team API keys and quotas). **Done (MVP)** — `TERMIT_TEAM_QUOTAS`, team usage API, shared team quota pool.
- Persistent task history DB (replace in-memory task store). **Done (MVP)**
- Retrieval + context compaction for long coding sessions. **Done (MVP)**

## High Impact, High Effort

- Multi-agent planner/executor/verifier with benchmark-driven routing. **Done (MVP)** — `POST /api/orchestration/run` (planner/executor/verifier/task_runner phases).
- Hosted deployment profile (Docker + reverse proxy + observability stack). **Done (MVP)** — `Dockerfile`, `docker-compose.yml`, `HOSTED_DEPLOYMENT.md`.
- Fine-tuned coding model adapter for domain-specific repos. **Done (MVP)** — repo model profiles + benchmark routing policy API.

## Prioritized Next 4 Weeks

1. Week 1: task history persistence + UI task console. **Done (MVP)** — SQLite task store, `GET /api/tasks`, web Task console.
2. Week 2: eval automation pipeline + weekly KPI report. **Done (MVP)** — 24 scenarios, `run-suite`, JSONL reports, KPI export script, eval UI panel.
3. Week 3: retrieval/context compaction for large codebases. **Done (MVP)** — `CodeRetrievalService`, `ContextCompactor`, retrieval API, chat/UI integration.
4. Week 4: private beta hardening (auth, quotas, incident drills). **Done (MVP)** — timing-safe auth, team labels, ops readiness/drill APIs, quota admin tools, security headers.
