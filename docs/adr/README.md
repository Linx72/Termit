# ADR Lifecycle for OSS Integrations

This directory stores Architecture Decision Records for OSS/model reuse in Termit.

## Naming Convention

- `ADR-OSS-<component-name>.md` for reuse and licensing decisions.
- Keep names stable after acceptance to preserve links from docs and CI.

## Required Sections

Each ADR must contain all sections enforced by `scripts/check_oss_guardrail.py`:

1. `## 1. Context`
2. `## 2. License & IP Analysis`
3. `## 3. Architecture Boundary`
4. `## 4. Security & Compliance`
5. `## 5. KPI Hypothesis`
6. `## 6. Decision`
7. `## 7. Rollback & Exit Strategy`

## Lifecycle States

- `draft`: not merged into runtime plan yet.
- `accepted`: approved for implementation under defined constraints.
- `superseded`: replaced by a newer ADR; keep file, add link to replacement.
- `rejected`: evaluated and intentionally not integrated.

Status is tracked in the `Decision` section text.

## Review Date Policy

- Every ADR must include `Expiration / review date: YYYY-MM-DD`.
- CI fails if the review date is missing or expired.
- Recommended cadence: quarterly review for adopted/adapted components.

## Merge Gate

Do not merge new OSS integration code unless:

1. `docs/OSS_REUSE_MATRIX.md` references the component.
2. ADR exists and is complete.
3. `python3 scripts/check_oss_guardrail.py` passes.
