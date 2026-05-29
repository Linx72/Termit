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

## Sprint 2 - Execution Loop v1 (In Progress)

Goals:
- implement orchestration loop;
- support planning, execution, and reporting phases.

Backlog:
- [x] Add task state machine (`queued/running/verify/done/failed`).
- [x] Add structured execution logs.
- [x] Add retry policy by error class.
- [x] Add deterministic report output format.

Definition of Done:
- [ ] 10 end-to-end tasks complete via API without manual patching.

## Sprint 3 - Safe Local Automation (In Progress)

Goals:
- enable local operations with strict safety rules.

Backlog:
- [x] Introduce command allowlist and path sandbox checks.
- [x] Add confirmation gates for risky operations.
- [x] Add dry-run mode and explain-why mode.
- [x] Add audit trail for each local action.

Definition of Done:
- [x] local automation works on curated tasks with zero unsafe execution in tests.

## Sprint 4 - Online Automation and Browser Tasks

Goals:
- deliver stable web-task automation flow.

Backlog:
- [ ] Add browser workflow adapter.
- [ ] Add evidence capture (snapshot/screenshot).
- [ ] Add blocker detection and user handoff flow.
- [ ] Add timeout and anti-loop protections.

Definition of Done:
- 8 online scenarios pass with deterministic reports.

## Sprint 5 - Quality, Latency, and Cost Optimization

Goals:
- improve response quality while reducing cost and latency.

Backlog:
- [ ] Add model routing policy by task complexity.
- [ ] Add caching for repetitive prompts and retrieval chunks.
- [ ] Add context compaction rules.
- [ ] Add fallback/circuit breaker.

Definition of Done:
- KPI trend improves for quality, latency, and cost in eval runs.

## Sprint 6 - Beta Readiness and Growth Planning

Goals:
- stabilize operations and define next-quarter growth.

Backlog:
- [ ] Add beta onboarding and feedback collection flow.
- [ ] Add incident triage runbook.
- [ ] Add KPI dashboard spec.
- [ ] Build Q2 roadmap by impact/effort scoring.

Definition of Done:
- beta-ready checklist complete;
- roadmap for next 12 weeks approved.
