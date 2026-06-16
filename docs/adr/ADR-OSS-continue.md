# ADR-OSS-continue

## 1. Context

- Component: Continue architecture patterns
- Type: code
- Source URL: https://github.com/continuedev/continue
- Version/Commit: main (pin commit before any code import)
- Owner: Termit clients/platform

## 2. License & IP Analysis

- SPDX license: Apache-2.0
- Commercial use: allowed
- SaaS/hosted restrictions: none in Apache-2.0
- Copyleft obligations (if any): none (retain notices; comply with Apache terms)
- Model/data provenance risks: low for architecture-level reuse

## 3. Architecture Boundary

- Integration mode: adapt
- Adapter boundary path in Termit: `clients/termit-client/`, `clients/termit-desktop/`, `app/api/routes/`
- Critical-path impact: medium
- Replaceability target: <= 2 weeks (yes, maintain message protocol wrappers)

## 4. Security & Compliance

- Dependency scan status: pending (only patterns planned now, not dependency import)
- Security review notes: keep strict API boundary and avoid direct trust of UI messages
- Privacy/compliance implications: low

## 5. KPI Hypothesis

- Expected quality uplift: +10% reduction in client-side state desync issues and faster feature delivery
- Expected cost impact: positive engineering cost reduction due to cleaner boundaries
- Expected latency impact: neutral
- Validation window: one release cycle with Desktop/VSCode parity checks

## 6. Decision

- Decision: go (adapt architecture, do not migrate whole stack)
- Rationale: strong fit for multi-client message routing with low legal risk
- Constraints: keep Termit API contracts authoritative
- Expiration / review date: 2026-09-30

## 7. Rollback & Exit Strategy

- Rollback trigger(s): client regressions in stream/apply flows, complexity increase without velocity gain
- Rollback steps: revert to existing message routing layer and keep only docs-level references
- Exit replacement candidate(s): native Termit protocol evolution without external pattern borrow
