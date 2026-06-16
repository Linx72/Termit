# Termit Hosted Deployment Profile (MVP)

## Docker Compose (Termit + Caddy)

1. Copy env: `cp .env.example .env`
2. Build and run:

```bash
docker compose up --build -d
```

3. Verify through the proxy:
   - `GET http://localhost:8080/health`
   - `GET http://localhost:8080/api/ops/readiness`

Termit listens on **8765** inside the compose network; Caddy exposes **8080** (HTTP) and **80/443** when `TERMIT_PUBLIC_DOMAIN` is set.

## TLS / public domain

In `.env` or shell:

```bash
export TERMIT_PUBLIC_DOMAIN=termit.example.com
export TERMIT_ACME_EMAIL=ops@example.com
docker compose up --build -d
```

Caddy obtains certificates automatically for `TERMIT_PUBLIC_DOMAIN`. Local-only testing can omit the domain and use port 8080 only.

## Recommended production settings

- `TERMIT_AUTH_ENABLED=true`
- `TERMIT_API_KEYS=<key>:<quota>:<role>:<team>`
- `TERMIT_TEAM_QUOTAS=core:10000,beta:3000`
- Mount `./data` for feedback, finetune artifacts, and seed JSON
- Persist SQLite DB files on a volume (`termit-sqlite` volume in compose)

## Fine-tune pipeline (MVP)

1. Export dataset: `POST /api/finetune/datasets/export` or `python scripts/finetune_export.py`
2. Create job: `POST /api/finetune/jobs`
3. Validate dataset: `POST /api/finetune/jobs/{job_id}/run`
4. Train externally (Ollama Modelfile / HF / Unsloth) using `GET /api/finetune/recipe`
5. Register adapter: `POST /api/finetune/adapters` (optionally updates repo routing profile)

## Observability hooks

- Health: `/health`
- Readiness: `/api/ops/readiness`
- Metrics: `/api/metrics`
- KPI snapshots: `POST /api/metrics/snapshot`
- Incident drill: `POST /api/ops/incident-drill` (admin key)

## Hosted beta smoke (post-deploy)

After `docker compose up --build -d`:

```bash
chmod +x ./scripts/hosted_smoke.sh
./scripts/hosted_smoke.sh
```

With production auth profile (`deploy/docker.env.example` copied into `.env`):

```bash
TERMIT_API_KEY=viewer-key TERMIT_HOSTED_AUTH_EXPECT=true ./scripts/hosted_smoke.sh
```

Checks: proxy reachability, health/readiness/metrics, `X-Trace-Id` header, optional auth 401 without key.

Optional Media Studio gate (requires `TERMIT_MEDIA_ENABLED=true` in `.env`):

```bash
TERMIT_MEDIA_ENABLED=true TERMIT_HOSTED_MEDIA_EXPECT=true ./scripts/hosted_smoke.sh
```

For Fal I2V in hosted deploy, set `TERMIT_MEDIA_PUBLIC_BASE_URL` to your public API origin (e.g. `https://your-domain.example`).

Production overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
TERMIT_HOSTED_BASE_URL=http://127.0.0.1:8080 ./scripts/hosted_smoke.sh
```

Recommended prod env extras: `TERMIT_LOG_JSON=true`, SQLite backup cron (`scripts/backup_sqlite.sh`).

## Upgrade flow

1. `docker compose pull && docker compose up --build -d`
2. Run incident drill and eval suite smoke checks
3. Compare KPI trend (`GET /api/metrics/trend`)
