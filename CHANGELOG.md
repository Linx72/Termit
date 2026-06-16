# Changelog

## [0.3.6] - 2026-06-16

### Added
- **Desktop:** `RuntimeStatusBar` (active runs, queue, workers, outcome classes); Quick Start wizard; DLQ list/replay in `AgentObservabilityPanel`
- **Observability:** Prometheus SLO metrics (`termit_agent_dead_letter_rate`, stale runs, completion rate); Grafana dashboard + alert rules; `docker-compose.monitoring.yml`
- **Release ops:** `scripts/release_pack.sh`, `docs/RELEASE_FLOW.md`, `scripts/backup_sqlite.sh`, `docker-compose.prod.yml`
- **SDK:** `listDlqRuns`, `replayDlqRuns`, `replayAgentRun` in `@termit/client`

### Changed
- Eval parity scenarios marked complete (74 scenarios in `data/eval_scenarios.json`)
- Unstable e2e integration tests gated behind `TERMIT_RUN_UNSTABLE_INTEGRATION=1` (nightly only)
- Graceful agent worker shutdown with configurable grace period
- Secret/credential patterns blocked in patch content via guardrails

### Security
- Tool audit export from desktop settings (admin role)
- API key quota summary panel for admin keys
- Signed desktop release pipeline: codesign + notarization for `TermitShell.app` (see `docs/DESKTOP_SIGNING_RU.md`)


## [0.3.4] - 2026-06-04

### Fixed
- Stabilized release smoke e2e polling for background agent runs in `tests/test_agents_api.py` and `tests/test_platform_e2e.py` to avoid transient `running` state flakes under load.
- Ensured eval patch fixture baseline is always restored after each scenario run in `app/services/eval_service.py` (`finally` reset path).
- Confirmed release scripts run Python checks via repository virtualenv for consistent dependency resolution across environments.

### Reliability
- Full release contour (`release_smoke.sh` + push + tag + release) now completes deterministically with parity gates enabled.

## [0.3.3] - 2026-06-04

### Added
- Runtime queue stuck SLA metrics in `/api/ops/agent-runs/metrics` (`stale_queued_runs`, `stale_running_runs`, `max_queued_age_seconds`, `max_running_age_seconds`, `queue_stuck_timeout_seconds`)
- New config knob `TERMIT_AGENT_QUEUE_STUCK_TIMEOUT_SECONDS` for queue watchdog visibility threshold
- Desktop default stable profile template `desktop-cursor-parity-stable` for Cursor-like autonomous coding path
- Cursor parity eval pack (`category=cursor_parity`, 20 scenarios CP1..CP20)

### Changed
- Tool loop determinism: `run_mode=plan` now blocks mutating tools (`apply_patch`, `execute_command`) with explicit phase-guard event
- Desktop activity tape now includes periodic heartbeat while run is in progress
- CI/release smoke now enforce Cursor parity eval gate before full eval suite
- Agent Hub health summary now includes completion rate and run lifecycle dwell/stale indicators

### Notes
- This release is parity-focused and does not change public API authentication semantics.

## [0.3.2] - 2026-05-31

### Added
- **Dual-pass chat** (`TERMIT_DUAL_PASS_ENABLED`): draft model + review validator for coding/review/debug
- **FIM completion API** `POST /api/completion/fim` — fast tab completion path for clients
- **Tasks → agent bridge** (`TERMIT_TASK_USE_AGENT`, `TERMIT_TASK_AGENT_ID`): auto tasks delegate to agent run
- Eval scenarios C4–C5 (patch dry-run / verify failure cases)
- `@termit/client`: `fimComplete()`, `requestTabCompletion` prefers FIM endpoint

### Changed
- Phase 1 brain roadmap items documented; semantic retrieval + agent verify already in 0.3.1

## [0.3.1] - 2026-05-31

### Added
- Finetune dataset curator (dedupe, quality filter, stratified export)
- `scripts/release_all.sh` — one-shot tests, smoke, push, GitHub release
- VS Code extension publishing guide (`clients/vscode-extension/PUBLISHING.md`)

### Changed
- Dataset export pulls from feedback, tasks, agent runs, and chat sessions with curation stats

## [0.3.0] - 2026-05-31

### Added
- TypeScript SDK workflows: `watchAgentRun` (SSE), `fetchInlineEditPatch`, `requestTabCompletion`, `computePatchedContent`
- VS Code extension v0.4.0: Chat, Composer, Cmd+Alt+K inline edit, tab completion, agent timeline via SSE
- Desktop app v0.4.0: Monaco Editor tab, Cmd+K inline edit, tab completion, agent timeline via SSE
- Stage1 finetune pipeline API, scheduler scripts, and weekly automation hooks
- Agent maintenance scheduler, alert health thresholds, request trace middleware
- Release smoke script (`scripts/release_smoke.sh`) and weekly eval helper (`scripts/weekly_eval.sh`)

### Changed
- Agent run UI uses SSE (`GET /api/agents/runs/{id}/stream`) instead of 2s polling
- Shared patch/completion logic consolidated in `@termit/client`

## [0.2.0] - 2026-05-30

### Added
- Team workspaces with shared daily quotas (`TERMIT_TEAM_QUOTAS`)
- Multi-agent orchestration API (`POST /api/orchestration/run`)
- Repo model profiles and benchmark-driven routing
- Fine-tune pipeline: dataset export, job tracking, adapter registration
- Docker Compose stack with Caddy reverse proxy
- Ops readiness and incident drill APIs
- Eval automation for 24 scenarios
- SQLite persistence for tasks, memory, agent runs, quotas

### Changed
- Chat supports retrieval, context compaction, and routing policies
- Auth uses constant-time API key comparison and security headers

## [0.1.0] - 2026-05-30

### Added
- Initial Termit MVP: FastAPI backend, web UI, task lifecycle, tooling, eval harness
