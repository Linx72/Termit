# Observability Checklist (Sprint 1)

## Metrics

- [x] request count by endpoint — `GET /api/metrics/prometheus` (`termit_http_requests_total`)
- [x] success/error rate by endpoint — `termit_http_errors_total`
- [ ] task success rate by scenario type — eval dashboard / finetune KPI
- [x] p50/p95 latency — `termit_http_latency_p95_ms`, chat p95 gauge
- [x] provider fallback rate — `termit_chat_fallback_rate` + alert
- [ ] cost per task and cost per success — routing cost-aware (optional)

## Tracing

- [x] request trace id propagation — trace middleware
- [x] tool invocation spans — `TraceSpanStore`, platform spans API
- [ ] model provider spans
- [ ] verification stage spans

## Logging

- [ ] structured logs (JSON preferred)
- [ ] error logs with stable error classes
- [x] audit logs for risky tool actions — `GET /api/tools/audit`
- [ ] redaction policy for sensitive data

## Alerting

- [x] high error-rate alert — Prometheus `TermitHighToolLoopErrors`, webhook dispatch
- [x] latency SLO breach alert — Grafana Termit SLO dashboard
- [ ] provider failure burst alert
- [x] safety policy violation alert — guardrails block + audit

## Dashboards

- [x] endpoint health dashboard — Grafana Termit SLO + `/api/metrics/http-endpoints`
- [ ] task quality dashboard — eval KPI (partial: HealthDashboard)
- [x] reliability dashboard — `/api/ops/readiness`, agent-runs metrics
- [x] cost and routing dashboard — Grafana cost signals + `termit_model_usage_total`

See [`docs/OBSERVABILITY_SLO_RU.md`](file:///Users/amoros/Projects/Termit/docs/OBSERVABILITY_SLO_RU.md).
