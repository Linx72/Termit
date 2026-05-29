# Eval Suite v1 (MVP)

## How to Use

- Run this suite weekly.
- Compare against previous run and baseline.
- Track pass rate, latency, cost, and automation level.

## Scoring Rubric

- `Task success` (0/1)
- `Answer quality` (1-5)
- `Safety compliance` (0/1)
- `Automation level` (manual assisted / semi-auto / full-auto)
- `Time to first useful output` (seconds)
- `Total task duration` (seconds)
- `Cost per task` (USD)

## Scenario Set (Initial 24)

### A. Coding (8)
- A1: implement missing function from docstring.
- A2: refactor duplicated logic into reusable helper.
- A3: write unit tests for existing module.
- A4: debug failing test with reproducible steps.
- A5: explain complex code section and propose simplification.
- A6: generate migration-safe API change patch.
- A7: optimize slow function with performance rationale.
- A8: produce PR-ready change summary from diff.

### B. Local Operations (8)
- L1: list project files by pattern.
- L2: read and summarize key config risks.
- L3: run test command and explain failures.
- L4: run formatter/linter and summarize changes.
- L5: prepare release notes from git history.
- L6: validate environment requirements before run.
- L7: create rollback plan for risky operation.
- L8: execute multi-step command sequence with checkpoints.

### C. Online Automation (8)
- W1: navigate to target page and collect structured info.
- W2: complete multi-step form with validation checks.
- W3: detect blocker and produce handoff instructions.
- W4: compare two pages and summarize diffs.
- W5: collect evidence (snapshot/screenshot) for final report.
- W6: extract task-relevant links and classify them.
- W7: reproduce issue via browser sequence and report root cause.
- W8: perform safe repetitive action with anti-loop constraints.

## Weekly KPI Targets (Trend-Based)

- pass rate increases week over week;
- p95 latency decreases or stays stable under higher load;
- cost per successful task decreases by routing optimization;
- safety compliance remains at 100%;
- full or semi-automated completions increase each week.

## Failure Taxonomy

- `planning_error`: wrong plan or missing dependency.
- `tool_error`: failed tool invocation or invalid inputs.
- `safety_block`: action blocked by policy.
- `verification_error`: output exists but fails checks.
- `external_error`: provider/network instability.

Each failed run must include:
- failure class;
- minimal reproducible context;
- concrete next fix action.
