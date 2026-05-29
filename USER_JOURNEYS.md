# Canonical User Journeys (MVP)

## 1) Implement Feature from Issue

User intent:
- provide task description or issue text;
- get code change ready for review.

Acceptance criteria:
- files modified are relevant;
- changes are explained;
- tests suggested or executed where applicable.

## 2) Fix Failing Test

User intent:
- share failing command or output;
- receive root cause and patch.

Acceptance criteria:
- root cause is identified;
- fix compiles/runs;
- report includes verification steps.

## 3) Refactor Legacy Module

User intent:
- improve readability/maintainability without behavior change.

Acceptance criteria:
- behavior remains stable;
- duplication is reduced;
- summary highlights migration risk (if any).

## 4) Perform Safe Local Automation

User intent:
- run a series of local commands for setup/build/test.

Acceptance criteria:
- only allowed commands are executed;
- risky steps require confirmation;
- output is summarized and actionable.

## 5) Execute Online Research Task

User intent:
- gather targeted data from web sources.

Acceptance criteria:
- sources are cited;
- extracted data is structured;
- blockers are explicitly reported.

## 6) Mixed Task: Code + Web + Local

User intent:
- investigate problem online, patch locally, verify with commands.

Acceptance criteria:
- workflow is split into clear phases;
- each phase has evidence;
- final report includes result and residual risk.

## 7) Prepare PR-Ready Summary

User intent:
- convert technical work into review-ready explanation.

Acceptance criteria:
- includes what changed and why;
- includes testing and known limitations;
- concise and readable for reviewers.
