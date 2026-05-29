# Observability Checklist (Sprint 1)

## Metrics

- [ ] request count by endpoint
- [ ] success/error rate by endpoint
- [ ] task success rate by scenario type
- [ ] p50/p95 latency
- [ ] provider fallback rate
- [ ] cost per task and cost per success

## Tracing

- [ ] request trace id propagation
- [ ] tool invocation spans
- [ ] model provider spans
- [ ] verification stage spans

## Logging

- [ ] structured logs (JSON preferred)
- [ ] error logs with stable error classes
- [ ] audit logs for risky tool actions
- [ ] redaction policy for sensitive data

## Alerting

- [ ] high error-rate alert
- [ ] latency SLO breach alert
- [ ] provider failure burst alert
- [ ] safety policy violation alert

## Dashboards

- [ ] endpoint health dashboard
- [ ] task quality dashboard
- [ ] reliability dashboard
- [ ] cost and routing dashboard
