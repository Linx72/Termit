# Termit Beta Onboarding

## Who This Beta Is For

- developers testing coding orchestration workflows;
- operators validating safe local automation;
- teams evaluating open-source model routing.

## 5-Minute Setup

1. Install dependencies and run server on port `8765`.
2. Configure `.env` model endpoints.
3. Open `http://localhost:8765`.
4. Optional auth:
   - `TERMIT_AUTH_ENABLED=true`
   - `TERMIT_API_KEYS=dev-key:1000:operator:my-team`
5. Run beta readiness check:
   - UI button `Check readiness`, or `GET /api/ops/readiness`
6. Paste API key in UI (stored in browser local storage).

## Client apps (optional)

Termit works as a backend; clients provide Cursor-like UX without Cursor billing:

| Client | Setup |
|--------|--------|
| **VS Code extension** | `cd clients/termit-client && npm i && npm run build` then `cd ../vscode-extension && npm i && npm run build` — press F5 |
| **Desktop app** | Same SDK build, then `cd clients/termit-desktop && npm i && npm run dev` |
| **TypeScript SDK** | `@termit/client` — chat, tasks, agents, `apply_patch`, workflows |

See [`clients/CLIENT_UX.md`](clients/CLIENT_UX.md). With auth enabled, set `termit.apiKey` / desktop API key to an **operator** key for patches.

## Hosted beta (Docker)

```bash
cp deploy/docker.env.example .env   # or cp .env.example .env
docker compose up --build -d
./scripts/hosted_smoke.sh
# With auth profile:
TERMIT_API_KEY=viewer-key TERMIT_HOSTED_AUTH_EXPECT=true ./scripts/hosted_smoke.sh
```

See [`HOSTED_DEPLOYMENT.md`](HOSTED_DEPLOYMENT.md).

## Weekly quality loop

```bash
./scripts/release_smoke.sh          # tests + health before release
./scripts/weekly_eval.sh          # eval suite + KPI snapshot
./scripts/stage1_weekly.sh        # finetune pipeline (optional)
```

## First Tasks to Try

1. Coding prompt (`task_type=coding`) with memory enabled.
2. Provider health check.
3. Session export (`markdown`, `txt`, `json`).
4. Submit beta feedback from UI or `POST /api/feedback`.
5. Run one eval scenario via `POST /api/eval/run`.

## What We Need From Beta Users

- task success/failure examples;
- unsafe behavior reports (if any);
- latency and quality notes;
- preferred model/provider combinations.

## Support Loop

- collect feedback in `TERMIT_FEEDBACK_FILE` (default `./data/feedback.jsonl`);
- triage weekly using `RELEASE_CHECKLIST.md`;
- prioritize fixes in `SPRINT_BACKLOG.md`.
