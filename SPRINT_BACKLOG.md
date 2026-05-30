# Sprint Backlog (6 Sprints)

Sprint length: 2 weeks.

## Sprint 1 - Foundation and Contracts (Completed)

Goals:
- define hard product scope for MVP;
- formalize architecture and module contracts;
- create baseline eval tasks.

Backlog:
- [x] Define 7 canonical user journeys.
- [x] Add API contract for task execution lifecycle.
- [x] Add tool safety policy (allowlist + risk levels).
- [x] Add benchmark specification.
- [x] Add initial observability checklist.

Definition of Done:
- docs merged;
- at least 20 eval cases prepared;
- each journey has pass/fail criteria.

## Sprint 2 - Execution Loop v1 (Completed)

Goals:
- implement orchestration loop;
- support planning, execution, and reporting phases.

Backlog:
- [x] Add task state machine (`queued/running/verify/done/failed`).
- [x] Add structured execution logs.
- [x] Add retry policy by error class.
- [x] Add deterministic report output format.

Definition of Done:
- [x] 10 end-to-end tasks complete via API without manual patching.

## Sprint 3 - Safe Local Automation (Completed)

Goals:
- enable local operations with strict safety rules.

Backlog:
- [x] Introduce command allowlist and path sandbox checks.
- [x] Add confirmation gates for risky operations.
- [x] Add dry-run mode and explain-why mode.
- [x] Add audit trail for each local action.

Definition of Done:
- [x] local automation works on curated tasks with zero unsafe execution in tests.

## Sprint 4 - Online Automation and Browser Tasks (Completed)

Goals:
- deliver stable web-task automation flow.

Backlog:
- [x] Add browser workflow adapter.
- [x] Add evidence capture (snapshot/screenshot).
- [x] Add blocker detection and user handoff flow.
- [x] Add timeout and anti-loop protections.

Definition of Done:
- [x] 8 online scenarios pass with deterministic reports.

## Sprint 5 - Quality, Latency, and Cost Optimization (Completed)

Goals:
- improve response quality while reducing cost and latency.

Backlog:
- [x] Add model routing policy by task complexity.
- [x] Add caching for repetitive prompts and retrieval chunks.
- [x] Add context compaction rules.
- [x] Add fallback/circuit breaker.

Definition of Done:
- [x] KPI trend improves for quality, latency, and cost in eval runs.

## Sprint 6 - Beta Readiness and Growth Planning (Completed)

Goals:
- stabilize operations and define next-quarter growth.

Backlog:
- [x] Add beta onboarding and feedback collection flow.
- [x] Add incident triage runbook.
- [x] Add KPI dashboard spec.
- [x] Build Q2 roadmap by impact/effort scoring.

Definition of Done:
- [x] beta-ready checklist complete;
- [x] roadmap for next 12 weeks approved.
