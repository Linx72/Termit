# ADR-OSS-mini-swe-agent

## 1. Context

- Component: mini-swe-agent
- Type: code
- Source URL: https://github.com/SWE-agent/mini-swe-agent
- Version/Commit: main (pin commit before integration)
- Owner: Termit platform

## 2. License & IP Analysis

- SPDX license: MIT
- Commercial use: allowed
- SaaS/hosted restrictions: no explicit restriction found in MIT
- Copyleft obligations (if any): none
- Model/data provenance risks: low (control-loop patterns only)

## 3. Architecture Boundary

- Integration mode: adopt (control-loop style and benchmark harness approach)
- Adapter boundary path in Termit: `app/services/multi_agent_orchestrator.py`, `app/services/eval_service.py`
- Critical-path impact: medium
- Replaceability target: <= 2 weeks (yes, keep wrapper in Termit modules)

## 4. Security & Compliance

- Dependency scan status: pending (evaluate only selected modules, avoid large dependency import)
- Security review notes: keep command execution policy inside Termit tooling service
- Privacy/compliance implications: low

## 5. KPI Hypothesis

- Expected quality uplift: +6 to +15 percentage points on repo-level bugfix scenarios in eval
- Expected cost impact: positive (simpler control flow means fewer failed retries)
- Expected latency impact: neutral
- Validation window: 2-week benchmark pass in fast/deep gates

## 6. Decision

- Decision: go (adopt selected loop ideas first)
- Rationale: fastest path to measurable coding-agent improvements with minimal complexity
- Constraints: no hard dependency on upstream package internals
- Expiration / review date: 2026-09-30

## 7. Rollback & Exit Strategy

- Rollback trigger(s): no KPI uplift after two eval cycles, increased flaky behavior
- Rollback steps: remove mini-style orchestration path and keep existing Termit orchestrator
- Exit replacement candidate(s): OpenHands-inspired event loop adaptation
