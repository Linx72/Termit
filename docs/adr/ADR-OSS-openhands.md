# ADR-OSS-openhands

## 1. Context

- Component: OpenHands (architecture patterns)
- Type: code
- Source URL: https://github.com/OpenHands/OpenHands
- Version/Commit: main (evaluate pinned commit during implementation)
- Owner: Termit platform

## 2. License & IP Analysis

- SPDX license: MIT
- Commercial use: allowed
- SaaS/hosted restrictions: no explicit restriction found in MIT
- Copyleft obligations (if any): none
- Model/data provenance risks: medium (framework-level integration is safe, but optional bundled configs/providers should be reviewed per dependency)

## 3. Architecture Boundary

- Integration mode: adapt
- Adapter boundary path in Termit: `app/services/agent_loop_service.py`, `app/services/agent_service.py`
- Critical-path impact: high
- Replaceability target: <= 2 weeks (yes, by keeping an internal action-observation contract)

## 4. Security & Compliance

- Dependency scan status: pending (not yet vendored)
- Security review notes: enforce sandbox-only runtime for destructive actions; keep risky tools behind confirm
- Privacy/compliance implications: low if no hosted OpenHands service is used

## 5. KPI Hypothesis

- Expected quality uplift: +5 to +12 percentage points on coding run completion (tool loop reliability + event structure)
- Expected cost impact: neutral to slightly positive by reducing retries
- Expected latency impact: +5-10% overhead per run (more structured orchestration)
- Validation window: 2-week shadow mode on coding tasks

## 6. Decision

- Decision: go (adapt patterns, not wholesale migration)
- Rationale: high architectural fit with Termit event/tool loop, but full framework adoption is unnecessary
- Constraints: no direct runtime dependency until adapter contract is stable
- Expiration / review date: 2026-09-30

## 7. Rollback & Exit Strategy

- Rollback trigger(s): increased failure rate, latency regression >15%, unsafe action rate increase
- Rollback steps: disable OpenHands-derived control flow via feature flag, return to native loop
- Exit replacement candidate(s): internal Termit loop only, mini-swe-agent style minimal loop
