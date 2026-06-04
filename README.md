# Termit

Open-source AI coding orchestrator MVP with task-based model routing.

**Русский старт:** [START_HERE_RU.md](START_HERE_RU.md)

## What is included

- FastAPI backend with `/api/chat`, `/api/chat/stream` and `/api/providers`
- Provider health endpoint:
  - `GET /api/providers/status`
- Session memory endpoints:
  - `GET /api/sessions/{session_id}`
  - `DELETE /api/sessions/{session_id}`
  - `GET /api/sessions/{session_id}/export`
- Task lifecycle endpoints:
  - `GET /api/tasks` (recent task history)
  - `POST /api/tasks`
  - `GET /api/tasks/{task_id}`
  - `GET /api/tasks/{task_id}/events`
  - `POST /api/tasks/{task_id}/cancel`
- Online automation endpoint:
  - `POST /api/automation/web`
- Metrics endpoint:
  - `GET /api/metrics`
  - `GET /api/metrics/thresholds` (public alert thresholds for chat + agent ops)
  - `GET /api/metrics/prometheus`
  - `POST /api/metrics/snapshot`
  - `GET /api/metrics/trend?days=7&limit=200`
  - `GET /api/metrics/daily-report?days=7&limit=200`
  - `GET /api/metrics/executive-summary?days=7&limit=200`
  - `GET /api/metrics/executive-summary/slack?days=7&limit=200`
  - `GET /api/metrics/executive-summary/slack/payload?days=7&limit=200`
- Basic agent tooling endpoints:
  - `GET /api/tools`
  - `POST /api/tools/list_files`
  - `POST /api/tools/read_file`
  - `POST /api/tools/execute_command`
  - `POST /api/tools/apply_patch`
  - `GET /api/tools/audit?limit=100`
- Local runtime management endpoints:
  - `GET /api/local/status`
  - `GET /api/local/models`
  - `POST /api/local/models/pull`
- Agent profile + execution endpoints:
  - `GET /api/agents`
  - `POST /api/agents`
  - `GET /api/agents/{agent_id}`
  - `POST /api/agents/{agent_id}/run`
  - `POST /api/agents/{agent_id}/runs` (enqueue background run)
  - `GET /api/agents/{agent_id}/runs`
  - `GET /api/agents/runs/{run_id}`
  - `GET /api/agents/runs/{run_id}/events`
  - `GET /api/agents/runs/{run_id}/stream` (SSE state stream)
  - `POST /api/agents/runs/{run_id}/cancel`
  - `POST /api/agents/{agent_id}/tools/list_files`
  - `POST /api/agents/{agent_id}/tools/read_file`
  - `POST /api/agents/{agent_id}/tools/execute_command`
  - `POST /api/agents/{agent_id}/tools/apply_patch`
- Task-based model router (`coding`, `review`, `debug`, `explain`, `general`)
- Provider adapters for local open-source runtimes:
  - `ollama:*` models
  - `openai_compat:*` models (for vLLM/TGI/LM Studio/OpenRouter-compatible local gateways)
- Minimal web UI at `/`

## Project structure

```text
app/
  api/routes/chat.py
  core/config.py
  domain/schemas.py
  services/
    chat_service.py
    model_router.py
    providers/
      base.py
      ollama_provider.py
      openai_compat_provider.py
  web/
    routes.py
    templates/index.html
  state.py
main.py
clients/
  termit-client/      # TypeScript SDK
  vscode-extension/   # VS Code extension (Chat, Composer, Cmd+Alt+K, agents)
  termit-desktop/     # Electron app (Monaco Editor, Composer, agents)
```

## Client integration

Termit is designed as an AI backend. External editors and apps connect over HTTP/SSE.  
See [`clients/CLIENT_UX.md`](clients/CLIENT_UX.md) for Cursor-like UX mapped to Termit APIs.

### apply_patch

Server-side file edits (operator role, confirmation required for writes):

```bash
curl -s -X POST http://127.0.0.1:8765/api/tools/apply_patch \
  -H 'Content-Type: application/json' \
  -d '{
    "path": "app/example.py",
    "hunks": [{"old_text": "old", "new_text": "new"}],
    "confirmed": true
  }'
```

- `hunks`: search/replace hunks (`old_text` must match exactly once)
- `content`: full file replacement (mutually exclusive with `hunks`)
- `create=true`: create a new file
- `dry_run=true`: preview without writing
- Sensitive paths (`.env`, `.git/`, `*.pem`, etc.) are blocked

Agents can call the same tool via `POST /api/agents/{agent_id}/tools/apply_patch` when `apply_patch` is in `enabled_tools`.

### TypeScript SDK

See [`clients/termit-client/README.md`](clients/termit-client/README.md).

```typescript
import { TermitClient } from "@termit/client";

const client = new TermitClient({ baseUrl: "http://127.0.0.1:8765" });
for await (const event of client.chatStream({ message: "Hello" })) {
  if (event.event === "token") process.stdout.write(String(event.data.text));
}
```

### VS Code extension

See [`clients/vscode-extension/README.md`](clients/vscode-extension/README.md) for build and F5 dev-host instructions.

Sidebar with **Chat / Composer / Tasks / Agents**, editor context (`@ file`), and **apply_patch** diff preview.

Settings: `termit.baseUrl`, `termit.apiKey`, `termit.includeEditorContext`.

### Desktop app (Termit) — основной клиент

See [`DESKTOP_QUICKSTART.md`](DESKTOP_QUICKSTART.md) and [`clients/termit-desktop/README.md`](clients/termit-desktop/README.md).

Electron app **Termit** — chat, composer, editor, tasks, agents via Termit API + local Ollama. No Cursor API key.

```bash
./scripts/run_termit_stack.sh          # Ollama + server + desktop dev
./scripts/package_desktop.sh           # build Termit.app in release/
```

## Multi-machine sync

Work on several computers via GitHub: see **[SYNC_WORKFLOW.md](SYNC_WORKFLOW.md)**.

```bash
./scripts/sync_start.sh                    # before work (pull --rebase)
./scripts/sync_finish.sh "what you changed" # commit + push
```

New machine: `./scripts/setup_new_machine.sh`

## Quick start

1. Copy environment:
   - `cp .env.example .env`
2. Install dependencies:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
3. Run server:
   - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8765`
4. Open:
   - [http://localhost:8765](http://localhost:8765)

5. Run tests:
   - `source .venv/bin/activate`
   - `python -m unittest discover -s tests -v`

## Help

### First run checklist

- Start backend and open `http://localhost:8765`.
- Verify provider connectivity with `GET /api/providers/status`.
- For local models, check `GET /api/local/models` and pull missing models via `POST /api/local/models/pull`.
- If auth is enabled, send `X-API-Key` with every `/api/*` request.

### Choosing execution mode

- Use `/api/chat` for direct model interaction.
- Use `/api/tasks` for plan/execute/verify/report lifecycle.
- Use `/api/agents/{agent_id}/run` for reusable agent profiles.
- Use `/api/agents/{agent_id}/runs` for background queue execution and `/api/agents/runs/{run_id}/stream` for live status.

### Agent permissions and online safety

- Keep `enabled_tools` minimal per agent (least privilege).
- For web tasks, set `allow_online=true` and include `web_automation` in `enabled_tools`.
- Online run payload should include:
  - `online_url`
  - optional `online_objective`
- Time/step limits are controlled by profile fields:
  - `online_timeout_seconds`
  - `online_max_steps`
  - `online_capture_links_limit`

### Common issues

- `429` responses: API key or team quota exhausted.
- Agent run state `failed`: read `error` field from run record.
- Empty agent output: verify model availability and fallback config.
- Tool denial (`403`): required tool is not in the agent allowlist.

## Routing behavior

- If `model` is provided in request, router uses it directly.
- Without explicit `model`:
  - `coding` -> `TERMIT_CODE_MODEL`
  - `review`, `debug`, `explain` -> `TERMIT_ANALYSIS_MODEL`
  - others -> `TERMIT_DEFAULT_MODEL`
- For high-complexity prompts (long context or architecture/security-style requests),
  router prioritizes analysis-grade models before default fallbacks.
- If primary model fails and request did not force `model`, router tries fallback:
  - `TERMIT_CODE_FALLBACK_MODEL`
  - `TERMIT_ANALYSIS_FALLBACK_MODEL`
  - `TERMIT_DEFAULT_FALLBACK_MODEL`

Use model naming format `provider:model_name`, e.g.:
- `ollama:termit-core-ft` (runtime / agents — finetuned Termit weights)
- `ollama:qwen2.5-coder` (runtime fallback)
- `TERMIT_TEACHER_MODEL=ollama:deepseek-coder` (stage-1 finetune only; excluded from chat routing)
- `openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct`

## Session memory

- Set `use_memory=true` in `/api/chat` (default enabled).
- If `session_id` is omitted, API auto-generates one and returns it.
- Conversation context is persisted per session via configurable backend:
  - `TERMIT_MEMORY_BACKEND=sqlite` (default)
  - `TERMIT_MEMORY_BACKEND=memory` (ephemeral in-process)
- SQLite path and retention are configured with:
  - `TERMIT_MEMORY_SQLITE_PATH`
  - `TERMIT_MEMORY_MAX_MESSAGES`
- Session export endpoint:
  - `GET /api/sessions/{session_id}/export?format=markdown|txt|json`

## Streaming chat

- `POST /api/chat/stream` returns Server-Sent Events.
- Event types:
  - `meta` (selected model/provider/session metadata)
  - `token` (chunked text payload)
  - `error` (provider/connectivity failure details)
  - `done` (stream completion marker)

## Task lifecycle behavior

- `mode=auto` runs plan -> execute -> verify -> report in one call.
- `mode=guided` creates a running task and pauses for step-by-step control.
- Task history is persisted via configurable backend:
  - `TERMIT_TASK_BACKEND=sqlite` (default)
  - `TERMIT_TASK_BACKEND=memory` (ephemeral in-process)
- SQLite path: `TERMIT_TASK_SQLITE_PATH`
- Agent profile registry path: `TERMIT_AGENT_REGISTRY_FILE`
- Agent background queue controls:
  - `TERMIT_AGENT_MAX_CONCURRENCY`
  - `TERMIT_AGENT_MAX_QUEUE_SIZE`
  - `TERMIT_AGENT_RUN_MAX_ATTEMPTS`
  - `TERMIT_AGENT_RUN_RETRY_BACKOFF_MS`
  - `TERMIT_AGENT_RUN_MAX_EVENTS_PER_RUN`
  - `TERMIT_AGENT_RUN_MAX_RESPONSE_CHARS`
  - `TERMIT_AGENT_RUN_RETENTION_DAYS`
  - `TERMIT_AGENT_MAINTENANCE_ENABLED`
  - `TERMIT_AGENT_CLEANUP_INTERVAL_SECONDS`
  - `TERMIT_AGENT_METRICS_SNAPSHOT_INTERVAL_SECONDS`
- Agent run persistence backend:
  - `TERMIT_AGENT_RUN_BACKEND=sqlite|memory`
  - `TERMIT_AGENT_RUN_SQLITE_PATH`
- Web UI includes a **Task console** section for create/list/refresh/cancel.
- Task status includes:
  - `attempts` and `max_attempts`
  - `failure_class` and `error` on failure
  - `events` timeline for execution diagnostics

## API auth and quotas

- Enable auth with `TERMIT_AUTH_ENABLED=true`
- Configure keys, quotas, roles, and optional team labels:
  - `TERMIT_API_KEYS=dev-key:1000:admin:core,viewer-key:300:viewer:beta`
- API keys are validated with constant-time comparison.
- Roles:
  - `viewer` (read/chat/export/feedback)
  - `operator` (+ tasks/tools execute/automation/eval run)
  - `admin` (+ session delete, tools audit)
- Send key via `X-API-Key` header or `Authorization: Bearer <key>`
- Protected routes: all `/api/*` except public health/docs
- Quota exceeded returns HTTP `429`
- Usage status endpoint:
  - `GET /api/usage` (includes `team` and `usage_percent`)
- Team workspaces (shared daily quota per team):
  - `TERMIT_TEAM_QUOTAS=core:5000,beta:2000`
  - `GET /api/teams`
  - `GET /api/teams/usage` (viewer: own team, admin: all)
- Repo-specific model routing:
  - `data/repo_model_profiles.json` + `TERMIT_REPO_MODEL_PROFILES_PATH`
  - `GET /api/routing/profiles`, `GET /api/routing/benchmarks`
  - Chat flags: `repo_profile`, `routing_policy=default|benchmark`
- Multi-agent orchestration:
  - `POST /api/orchestration/run` (planner → executor → verifier → task_runner)
- Fine-tune pipeline (MVP):
  - `POST /api/finetune/datasets/export`
  - `POST /api/finetune/jobs`, `POST /api/finetune/jobs/{job_id}/run`
  - `POST /api/finetune/adapters`, `GET /api/finetune/recipe`
  - `POST /api/finetune/pipeline/stage1-run` (auto: export -> baseline eval -> job validate -> recipe -> optional adapter register)
  - `POST /api/finetune/pipeline/stage1-runs` (enqueue stage1 pipeline in background)
  - `GET /api/finetune/pipeline/stage1-runs` (list pipeline runs; optional `status=failed`)
  - `GET /api/finetune/pipeline/stage1-runs/{run_id}` (poll progress/status)
  - `GET /api/finetune/pipeline/stage1-runs/{run_id}/stream` (SSE progress stream)
  - `POST /api/finetune/pipeline/stage1-runs/{run_id}/retry` (re-queue failed run)
  - `POST /api/finetune/pipeline/stage1-runs/{run_id}/cancel` (cancel queued run)
  - `GET /api/finetune/pipeline/stage1-scheduler/status` (built-in scheduler status)
  - `POST /api/finetune/pipeline/stage1-scheduler/trigger` (manual scheduler trigger)
  - CLI: `python3 scripts/finetune_export.py --name termit-export`
  - CLI: `python3 scripts/stage1_enqueue.py --from-env` (external schedulers)
  - Install schedulers: `./scripts/install_stage1_scheduler.sh all`
- Hosted deployment:
  - `docker compose up --build` — Caddy on `:8080`, Termit internal `:8765` (see `HOSTED_DEPLOYMENT.md`)
- Beta ops / incident drills:
  - `GET /healthz` (public dependency health probe)
  - `GET /api/ops/readiness` (public)
  - `POST /api/ops/incident-drill` (admin)
  - `GET /api/ops/quota-summary` (admin)
  - `POST /api/ops/quota/reset` (admin)
  - CLI: `python3 scripts/run_incident_drill.py --api-key <admin-key>`

## Reliability features

- Provider circuit breaker:
  - `TERMIT_CIRCUIT_FAILURE_THRESHOLD`
  - `TERMIT_CIRCUIT_COOLDOWN_SECONDS`
- Provider retry for transient generation errors:
  - `TERMIT_PROVIDER_RETRY_ATTEMPTS`
  - `TERMIT_PROVIDER_RETRY_BACKOFF_MS`
- Chat response cache for repeated non-memory requests (memory or sqlite TTL cache):
  - `TERMIT_RESPONSE_CACHE_BACKEND`
  - `TERMIT_RESPONSE_CACHE_SQLITE_PATH`
  - `TERMIT_RESPONSE_CACHE_TTL_SECONDS`
- Context compaction with summary of dropped history when message/char budgets are exceeded.
- Codebase retrieval (keyword index over workspace files) injects relevant snippets into chat:
  - `POST /api/retrieval/search`
  - `POST /api/retrieval/reindex`
  - `GET /api/retrieval/stats`
  - Chat flag: `use_retrieval=true` (+ optional `retrieval_path_prefix`)
  - Optional semantic mode: `TERMIT_RETRIEVAL_MODE=semantic` (Ollama `/api/embeddings`, SQLite cache in `data/`, keyword fallback)
- Agent tool loop can run post-patch verify: `TERMIT_AGENT_VERIFY_AFTER_PATCH`, `TERMIT_AGENT_VERIFY_CMD` (events: `patch_verify`, `tool_loop_step`)
- Dual-pass chat: `TERMIT_DUAL_PASS_ENABLED`, `TERMIT_DUAL_PASS_TASK_TYPES` (draft + review validator)
- Fast tab completion: `POST /api/completion/fim` (used by `@termit/client` `fimComplete`)
- Tasks auto → agent: `TERMIT_TASK_USE_AGENT`, `TERMIT_TASK_AGENT_ID`
- Telemetry retention configuration:
  - `TERMIT_TELEMETRY_MAX_LATENCY_POINTS`
- Telemetry quality signals now include empty response rate, code response rate, fallback rate,
  and average response length.
- `degraded` status thresholds for executive summary are configurable via:
  - `TERMIT_DEGRADE_EMPTY_RATE` (default `0.05`)
  - `TERMIT_DEGRADE_FALLBACK_RATE` (default `0.35`)
- Agent ops alert thresholds (queue/dead-letter/worker availability):
  - `TERMIT_AGENT_ALERT_QUEUE_UTILIZATION_PERCENT` (default `80`)
  - `TERMIT_AGENT_ALERT_DEAD_LETTER_RATE` (default `0.15`)
  - `TERMIT_AGENT_ALERT_MIN_WORKER_ALIVE_RATIO` (default `1.0`)
  - `TERMIT_FINETUNE_PIPELINE_MAX_CONCURRENCY` (default `1`, max parallel stage1 pipeline workers)
- Stage1 weekly scheduler options:
  - Built-in (inside Termit): `TERMIT_STAGE1_SCHEDULE_ENABLED=true`
  - External: `./scripts/install_stage1_scheduler.sh launchd|cron|github`
  - Shared external env: `deploy/schedulers/stage1-weekly.env.example`
- Continuous model training (Stage1 + Ollama):
  - Built-in trainer: `TERMIT_FINETUNE_AUTO_TRAIN=true` runs `ollama create` after each Stage1 run
  - Manual train API: `POST /api/finetune/jobs/{job_id}/train`, `POST /api/finetune/pipeline/stage1-runs/{run_id}/train`
  - Full loop script: `./scripts/stage1_full_loop.sh` (enqueue → wait → train → eval)
  - Post-train only: `./scripts/post_stage1_train.sh RUN_ID --wait --auto-register-adapter`
  - Trainer modes: `ollama` (auto), `modelfile` (write Modelfile only), `off`
  - Dataset export auto-curation (non-destructive): dedupe by instruction, quality filters, chat sessions + tool trajectories, stratified balance; source SQLite/feedback files are never modified
  - Auto-capture training signals on completed tasks/agent runs (`data/finetune/training_signals.jsonl`, append-only)
  - Eval-passed boost: samples linked to passed eval scenarios get higher export priority
  - Auto post-train eval when `TERMIT_FINETUNE_AUTO_TRAIN=true` and `TERMIT_FINETUNE_AUTO_POST_EVAL=true`
  - Regression gate blocks adapter promotion on eval regression; shadow model at `TERMIT_FINETUNE_SHADOW_TRAFFIC_PERCENT`
  - Training dashboard: `GET /api/finetune/training/dashboard`
  - Agent DLQ replay: `GET /api/agents/runs/dlq`, `POST /api/agents/runs/dlq/replay`, `POST /api/agents/runs/{id}/replay`
  - HF trainer mode: `TERMIT_FINETUNE_TRAINER=hf` generates QLoRA shell script
  - HTTP endpoint metrics: `GET /api/metrics/http-endpoints`, Prometheus p95 per route
  - Ops alert webhook: `POST /api/ops/alerts/dispatch` + `TERMIT_ALERT_WEBHOOK_URL`
  - Hosted docker profile: `deploy/docker.env.example` (auth enabled by default)
  - CI: `.github/workflows/agent-eval.yml`
- Metrics snapshot export file:
  - `TERMIT_METRICS_SNAPSHOT_FILE`
- Beta feedback endpoint:
  - `POST /api/feedback`
- Cross-platform dev (apps/games, atomic steps):
  - `GET /api/dev/cross-platform/stacks`
  - `POST /api/dev/cross-platform/decompose`
  - Guide: `docs/CROSS_PLATFORM_DEV_RU.md`
- Eval harness endpoints (53 scenarios in `data/eval_scenarios.json`):
  - `GET /api/eval/scenarios`
  - `POST /api/eval/run` (executes task/tool/web runner and returns scored result)
  - `POST /api/eval/run-suite` (batch run + JSONL report in `TERMIT_EVAL_REPORT_FILE`)
  - `GET /api/eval/reports?limit=10`
  - Weekly KPI export script: `python3 scripts/export_kpi_snapshot.py --capture`
- Metrics dashboard data endpoint:
  - `GET /api/metrics`
  - `POST /api/metrics/snapshot` stores a point-in-time KPI snapshot to JSONL
  - `GET /api/metrics/trend` returns trend points for dashboard charts
  - `GET /api/metrics/daily-report` returns latest-vs-previous KPI deltas
  - `GET /api/metrics/executive-summary` returns KPI status (`improving/mixed/stable/regressing`) with highlights
  - `GET /api/metrics/executive-summary/slack` returns Slack-ready summary text
  - `GET /api/metrics/executive-summary/slack/payload` returns Incoming Webhook-ready JSON payload

## Snapshot automation

- Run one-off snapshot capture:
  - `python scripts/metrics_report.py --mode snapshot`
- Print daily KPI report:
  - `python scripts/metrics_report.py --mode daily-report --days 7`
- Print executive KPI summary:
  - `python scripts/metrics_report.py --mode executive-summary --days 7`
- Print Slack-ready KPI summary text:
  - `python scripts/metrics_report.py --mode slack-summary --days 7`
- Print Slack webhook payload JSON:
  - `python scripts/metrics_report.py --mode slack-payload --days 7`
- Example cron (every hour):
  - `0 * * * * cd /path/to/Termit && /path/to/Termit/.venv/bin/python scripts/metrics_report.py --mode snapshot`

## Provider diagnostics

- `GET /api/providers/status` checks reachability of configured providers.
- UI button `Check providers` calls this endpoint and prints health details.
- UI supports export preview and download for session transcripts.

## Agent tools API

- `POST /api/tools/list_files` with `{ "path": ".", "pattern": "*.py" }`
- `POST /api/tools/read_file` with `{ "path": "app/main.py" }`
- `POST /api/tools/execute_command` with:
  - `{ "command": "python3 -c \"print('ok')\"", "path": ".", "dry_run": false, "confirmed": false }`
- command safety behavior:
  - `safe` commands execute immediately;
  - `confirm` commands require `confirmed=true`;
  - `blocked` commands never execute.
- `GET /api/tools/audit?limit=100` returns recent tool audit events.
- Paths are restricted to workspace root to prevent directory traversal.

## Local runtime API

- `GET /api/local/status` returns reachability for local providers (`ollama`, `openai_compat`).
- `GET /api/local/models` lists local models available in Ollama runtime.
- `POST /api/local/models/pull` with:
  - `{ "model": "ollama:qwen2.5-coder:14b" }`
  - also accepts plain model names, e.g. `{ "model": "qwen2.5-coder:14b" }`.

## Agent profiles API

- `POST /api/agents` creates reusable local agent profile with:
  - `name`, `description`, `system_prompt`
  - defaults for `task_type`, `model`, `temperature`, `max_tokens`, memory/retrieval flags
  - `enabled_tools` allowlist per agent (`list_files`, `read_file`, `execute_command`, `apply_patch`, `web_automation`)
  - online policy controls: `allow_online`, `online_max_steps`, `online_timeout_seconds`, `online_capture_links_limit`
- `GET /api/agents` lists registered agent profiles from local registry file.
- `POST /api/agents/{agent_id}/run` executes an agent profile on a new input:
  - merges profile defaults + per-run overrides
  - injects profile `system_prompt` as first system message.
  - supports online mode via run payload fields `online_url` + optional `online_objective`.
- `POST /api/agents/{agent_id}/runs` enqueues a background run and returns `run_id`.
- `GET /api/agents/runs/{run_id}` polls run state (`queued/running/completed/failed/cancelled`).
- `GET /api/agents/runs/{run_id}/events` returns detailed run timeline for retries/failures.
- `GET /api/agents/runs/{run_id}/stream` streams status updates via SSE until terminal state.
- `POST /api/agents/runs/{run_id}/cancel` cancels queued runs.
- Background runs use retry + backoff (`TERMIT_AGENT_RUN_MAX_ATTEMPTS`, `TERMIT_AGENT_RUN_RETRY_BACKOFF_MS`).
- If all retries fail, run is marked failed with `failure_class` and `run_dead_lettered` event.
- Run events are trimmed by policy (`TERMIT_AGENT_RUN_MAX_EVENTS_PER_RUN`) to keep storage bounded.
- Large run responses are truncated by policy (`TERMIT_AGENT_RUN_MAX_RESPONSE_CHARS`).

## Agent run operations

- `GET /api/ops/agent-runs/metrics` returns queue and worker metrics (viewer+ when auth enabled):
  - queue size/capacity/utilization
  - worker count and alive workers
  - total runs and state distribution
  - dead-letter rate + health status/reasons against active thresholds
- Web UI includes an **Operator dashboard** card row (queue, workers, dead-letter trend).
- `GET /healthz` returns dependency-level health (`memory/task/agent/quota sqlite`, providers, workers, maintenance, local runtime).
- `GET /api/metrics/thresholds` returns active chat + agent alert thresholds (public).
- `POST /api/ops/agent-runs/cleanup` (admin) applies retention cleanup:
  - payload: `{ "retention_days": 14, "dry_run": true }`
  - removes only terminal runs older than cutoff (`completed/failed/cancelled`)
  - returns deleted runs/events and remaining run count.
- `GET /api/ops/agent-runs/maintenance` returns maintenance scheduler status.
- `POST /api/ops/agent-runs/maintenance/cleanup-now` triggers one cleanup cycle.
- `GET /api/metrics/prometheus` exposes Prometheus-compatible metrics text.
- `POST /api/agents/{agent_id}/tools/web_automation` runs web automation with the agent's permissions.
- Tool proxy endpoints enforce per-agent permissions before delegating to tool safety policy.

## Online automation API

- `POST /api/automation/web` with:
  - `{ "url": "https://example.com", "objective": "Collect page evidence", "max_steps": 4, "timeout_seconds": 10 }`
- behavior:
  - captures evidence (`status_code`, `title`, `links`, `snapshot_excerpt`);
  - detects blockers (login/captcha/access denied);
  - enforces anti-loop guard via `max_steps`.

## Next steps

- Add tool-using agents (file editing, tests, lint, build pipelines)
- Add memory (session/history storage)
- Add evaluation harness (HumanEval/MBPP/custom suites)
- Add role-based access control and per-team billing metrics

## Execution artifacts

- `ROADMAP_90_DAYS.md` - phased execution plan with KPI targets
- `SPRINT_BACKLOG.md` - 6 sprint backlog with definitions of done
- `MVP_ARCHITECTURE.md` - architecture and module responsibilities
- `EVAL_SUITE.md` - initial 24 scenario evaluation suite
- `USER_JOURNEYS.md` - canonical end-to-end user journeys
- `TASK_EXECUTION_CONTRACT.md` - task lifecycle API contract draft
- `TOOL_SAFETY_POLICY.md` - safety and confirmation policy for tools
- `BENCHMARK_SPEC.md` - benchmark method and scoring
- `OBSERVABILITY_CHECKLIST.md` - metrics, traces, logging, alerts checklist
- `RELEASE_CHECKLIST.md` - release readiness and handoff checklist
- `SYNC_WORKFLOW.md` - daily Git sync across machines (GitHub)
- `BETA_ONBOARDING.md` - beta setup and first tasks
- `INCIDENT_RUNBOOK.md` - incident triage and recovery
- `KPI_DASHBOARD_SPEC.md` - KPI definitions and dashboard panels
