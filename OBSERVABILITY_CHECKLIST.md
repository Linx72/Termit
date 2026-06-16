# Observability Checklist (Sprint 1)

## Metrics

- [x] request count by endpoint — `GET /api/metrics/prometheus` (`termit_http_requests_total`)
- [x] success/error rate by endpoint — `termit_http_errors_total`
- [x] task success rate by scenario type — eval dashboard `pass_rate_by_category` + Prometheus
- [x] p50/p95 latency — `termit_http_latency_p95_ms`, chat p95 gauge
- [x] provider fallback rate — `termit_chat_fallback_rate` + alert
- [x] cost per task and cost per success — `termit_cost_per_successful_task_usd` gauge

## Tracing

- [x] request trace id propagation — trace middleware
- [x] tool invocation spans — `TraceSpanStore`, platform spans API
- [x] model provider spans — `provider.{name}` in TraceSpanStore during agent loop
- [x] verification stage spans — `verify.stage`, `verify.pass`, `verify.failed`, `verify.retry`

## Logging

- [x] structured logs (JSON preferred) — `TERMIT_LOG_JSON=true`, `app/core/structured_logging.py`
- [x] error logs with stable error classes — `error_class` in JsonLogFormatter
- [x] audit logs for risky tool actions — `GET /api/tools/audit`
- [x] redaction policy for sensitive data — `redact_sensitive()` in structured logging

## Alerting

- [x] high error-rate alert — Prometheus `TermitHighToolLoopErrors`, webhook dispatch
- [x] latency SLO breach alert — Grafana Termit SLO dashboard
- [x] provider failure burst alert — `TermitProviderFailureBurst` in `deploy/prometheus/alerts.yml`
- [x] safety policy violation alert — guardrails block + audit

## Dashboards

- [x] endpoint health dashboard — Grafana Termit SLO + `/api/metrics/http-endpoints`
- [x] task quality dashboard — eval KPI in HealthDashboard + KpiGatePanel
- [x] reliability dashboard — `/api/ops/readiness`, agent-runs metrics
- [x] cost and routing dashboard — Grafana cost signals + `termit_model_usage_total`

See [`docs/OBSERVABILITY_SLO_RU.md`](file:///Users/amoros/Projects/Termit/docs/OBSERVABILITY_SLO_RU.md).
