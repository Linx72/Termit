# OSS Reuse Matrix (Variant 2)

This matrix is the source of truth for reuse-first integrations.
Every row must have a linked ADR in `docs/adr/`.

## Decision Scale

- `adopt`: integrate as is with thin adapter.
- `adapt`: reuse patterns/code fragments behind Termit adapters.
- `monitor`: track ecosystem, do not integrate yet.
- `reject`: do not use in runtime path.

## Components

| Component | License (SPDX) | Initial Decision | Scope | Why | ADR |
| --- | --- | --- | --- | --- | --- |
| OpenHands core patterns | MIT | adapt | Agent runtime contract | Strong event/action/observation architecture, but full migration is too heavy. | [ADR-OSS-openhands](file:///Users/amoros/Projects/Termit/docs/adr/ADR-OSS-openhands.md) |
| mini-swe-agent | MIT | adopt | Control loop and benchmark harness style | Minimal and high ROI for repo-level coding flow with low complexity. | [ADR-OSS-mini-swe-agent](file:///Users/amoros/Projects/Termit/docs/adr/ADR-OSS-mini-swe-agent.md) |
| Continue architecture | Apache-2.0 | adapt | IDE message routing and Core-UI boundaries | Good fit for Desktop/VSCode parity via typed protocol ideas. | [ADR-OSS-continue](file:///Users/amoros/Projects/Termit/docs/adr/ADR-OSS-continue.md) |

## Mandatory Gate Before Merge

1. ADR exists and is complete (all required sections).
2. `scripts/check_oss_guardrail.py` passes.
3. Integration mode (`adopt/adapt/monitor/reject`) is explicit.
4. Exit strategy is documented.
5. Review date is set.
