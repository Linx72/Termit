# Termit 90-Day Execution Roadmap

## Product Goal

Build an AI coding orchestrator that can:
- write and review code;
- run safe local computer tasks;
- execute online automation tasks;
- complete user tasks with high reliability and low latency.

## Scope Guardrails

- Team model: solo founder.
- Budget mode: high (can use stronger models and infra).
- Primary KPI bundle: quality, latency, cost efficiency, reliability, retention.
- Additional KPI: automation rate (tasks completed with minimal user intervention).

## Phases

### Phase 1: Foundation (Weeks 1-2)

Deliverables:
- product spec with top 7 user journeys;
- execution modes (`plan`, `execute`, `verify`, `report`);
- secure tool policy (allowlist + confirmation levels);
- baseline benchmarks vs 2-3 alternatives.

Exit criteria:
- each user journey has acceptance criteria;
- baseline quality and latency metrics are measured and saved.

### Phase 2: Core MVP (Weeks 3-6)

Deliverables:
- robust chat API and streaming UX;
- model routing for coding/review/debug/explain/general;
- tool calling for files, shell tasks, and browser actions;
- session memory and task history;
- first orchestration loop (`plan -> execute -> verify -> report`).

Exit criteria:
- 20 core tasks reproducible end-to-end;
- failure handling and retries implemented.

### Phase 3: Quality and Optimization (Weeks 7-10)

Deliverables:
- evaluation harness and score dashboard;
- model routing optimization (fast model + strong validator pattern);
- caching, fallback chains, and circuit breaker;
- automated regression suite for critical flows.

Exit criteria:
- measurable quality increase over baseline;
- lower cost per completed task with equal or better quality.

### Phase 4: Beta and Scale Readiness (Weeks 11-12)

Deliverables:
- private beta with real user tasks;
- error taxonomy and triage loop;
- growth roadmap for Q2.

Exit criteria:
- stable beta operations;
- post-MVP roadmap prioritized by impact.

## KPI Targets by Day 90

- Task Success Rate: >= 75%.
- p95 Time to first useful token: < 3 seconds.
- Automation Rate: >= 60%.
- Reliability (service uptime): >= 99.5%.
- Cost per completed task: at least 25% better than week-2 baseline.
- D30 retention (beta cohort): >= 35%.

## Risk Register

- Tool safety regressions.
- High provider costs from overuse of premium models.
- Latency spikes from long-context requests.
- Flaky browser automation due to dynamic pages.

Mitigations:
- strict permission policy with escalation;
- dynamic model routing by task complexity;
- caching + prompt compaction;
- evidence-first retries and deterministic automation steps.
