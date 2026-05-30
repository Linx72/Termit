# KPI Dashboard Spec (MVP)

## Goal

Track product quality and operational health for Termit beta.

## Core Metrics

- Task Success Rate = completed tasks / total tasks.
- Automation Rate = tasks completed without manual intervention.
- p95 Time to First Useful Token (chat stream `meta` -> first `token`).
- Cost per Completed Task (model usage estimate).
- Reliability = successful health checks / total checks.
- Safety Compliance = unsafe tool actions blocked / total risky attempts.

## Data Sources

- API logs (request status, endpoint, latency).
- Task lifecycle events (`/api/tasks/{id}/events`).
- Tool audit trail (`/api/tools/audit`).
- Eval runs (`/api/eval/scenarios`, `/api/eval/run`).
- Feedback stream (`TERMIT_FEEDBACK_FILE`).
- Metrics API:
  - `GET /api/metrics`
  - `POST /api/metrics/snapshot`
  - `GET /api/metrics/trend`
  - `GET /api/metrics/daily-report`
  - `GET /api/metrics/executive-summary`
  - `GET /api/metrics/executive-summary/slack`
  - `GET /api/metrics/executive-summary/slack/payload`

## Dashboard Panels

1. **Reliability**
   - health uptime
   - provider availability (`/api/providers/status`)
2. **Execution Quality**
   - task pass/fail by category
   - failure taxonomy distribution
3. **Performance**
   - p50/p95 latency by endpoint
   - stream start latency
4. **Cost and Routing**
   - model usage share
   - fallback activation rate
5. **Safety**
   - blocked vs confirmed risky commands
   - policy violations over time

## Refresh Cadence

- realtime panel: health/providers (1 min)
- hourly: latency and error rates
- daily: cost, pass rate, feedback summary
- weekly: eval suite comparison

## MVP Implementation Notes

- start with JSONL/log aggregation scripts;
- export daily snapshot for trend charts;
- evolve to proper observability stack in Phase 4.
