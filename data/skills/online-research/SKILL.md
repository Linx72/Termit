---
name: Online Research
description: Fast or deep web research with citations for Termit agents
---

# Online Research

Use for **online_research** tasks: gather facts, compare sources, return structured notes — not full project delivery.

## Fast path

1. `web_search` — query + optional `domains`, `recency_days`
2. Open 2–3 top hits with `web_automation` (static HTML) or `browser_navigate` (JS)
3. Output: bullet summary + **citations** list + open questions

## Deep path

1. Broad `web_search`, then narrow queries
2. `browser_navigate` → `browser_snapshot` on pages that fail httpx fetch
3. Cross-check conflicting claims; note confidence

## Output format

```markdown
## Summary
...

## Sources
1. [title](url) — one-line takeaway
...

## Blockers
- (none) | login | captcha | ...
```

Always set `allow_online=true` on the agent profile.
