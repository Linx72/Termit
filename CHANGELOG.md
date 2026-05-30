# Changelog

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
