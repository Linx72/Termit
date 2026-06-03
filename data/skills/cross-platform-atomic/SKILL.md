---
name: Cross-platform atomic dev
description: Decompose iOS, macOS, Windows, Android apps and games into verifiable atomic steps
---

# Cross-platform atomic dev

Use when the user builds **apps or games** for **iOS, macOS, Windows, and/or Android**.

## Workflow

1. Call `POST /api/dev/cross-platform/decompose` with the user goal (optional `stack_id`, `platforms`).
2. Pick the returned `agent_template_id` and mount this skill.
3. Execute **one atomic task at a time**; after each step run the task's `verify_hint`.
4. Do not start the next platform shell until the previous step passes verify.

## Stacks

| stack_id | Use for |
|----------|---------|
| flutter | Shared UI for all four platforms |
| swift_multiplatform | Native Apple (iOS + macOS) |
| kotlin_compose | Android-first |
| unity / godot | Games |
| winui | Windows-only native |
| maui | .NET across mobile + desktop |

## Anti-patterns

- Monolithic PR spanning all platforms without per-step verify
- Skipping CI matrix until the end
- Mixing game loop changes with store release signing in one step
