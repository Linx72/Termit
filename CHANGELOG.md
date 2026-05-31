# Changelog

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
