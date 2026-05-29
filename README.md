# Termit

Open-source AI coding orchestrator MVP with task-based model routing.

## What is included

- FastAPI backend with `/api/chat`, `/api/chat/stream` and `/api/providers`
- Provider health endpoint:
  - `GET /api/providers/status`
- Session memory endpoints:
  - `GET /api/sessions/{session_id}`
  - `DELETE /api/sessions/{session_id}`
  - `GET /api/sessions/{session_id}/export`
- Task lifecycle endpoints:
  - `POST /api/tasks`
  - `GET /api/tasks/{task_id}`
  - `GET /api/tasks/{task_id}/events`
  - `POST /api/tasks/{task_id}/cancel`
- Basic agent tooling endpoints:
  - `GET /api/tools`
  - `POST /api/tools/list_files`
  - `POST /api/tools/read_file`
  - `POST /api/tools/execute_command`
  - `GET /api/tools/audit?limit=100`
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
```

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

## Routing behavior

- If `model` is provided in request, router uses it directly.
- Without explicit `model`:
  - `coding` -> `TERMIT_CODE_MODEL`
  - `review`, `debug`, `explain` -> `TERMIT_ANALYSIS_MODEL`
  - others -> `TERMIT_DEFAULT_MODEL`
- If primary model fails and request did not force `model`, router tries fallback:
  - `TERMIT_CODE_FALLBACK_MODEL`
  - `TERMIT_ANALYSIS_FALLBACK_MODEL`
  - `TERMIT_DEFAULT_FALLBACK_MODEL`

Use model naming format `provider:model_name`, e.g.:
- `ollama:deepseek-coder`
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
- Task status includes:
  - `attempts` and `max_attempts`
  - `failure_class` and `error` on failure
  - `events` timeline for execution diagnostics

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

## Next steps

- Add tool-using agents (file editing, tests, lint, build pipelines)
- Add memory (session/history storage)
- Add evaluation harness (HumanEval/MBPP/custom suites)
- Add auth and usage quotas for multi-user deployment

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
