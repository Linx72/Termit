# Benchmark Specification (MVP Baseline)

## Objective

Measure Termit against alternatives on real workflows:
- coding quality;
- automation reliability;
- latency;
- cost efficiency.

## Systems Under Test

- Termit (current branch build);
- 2-3 comparison systems selected by user context.

## Dataset

Use `EVAL_SUITE.md` initial set (24 scenarios):
- 8 coding;
- 8 local operations;
- 8 online automation.

## Method

For each scenario:
1. Run with identical prompt intent.
2. Collect structured outputs.
3. Score using shared rubric.

## Metrics

- success rate;
- quality score (1-5);
- safety compliance (0/1);
- p50/p95 latency;
- cost per successful task;
- automation rate (manual/semi/full).

## Reporting Format

- one row per scenario;
- aggregate by scenario type;
- trend vs previous week;
- top 5 failure reasons with count.

## Baseline Workflow

- week 1: establish baseline;
- weekly: rerun and compare deltas;
- release gate: no regression in safety and reliability metrics.
