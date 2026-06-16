---
name: Termit Next Iteration
description: Continue Termit roadmap end-to-end: reliability, eval gates, finetune loop, and release discipline
---

# Termit Next Iteration

Use this skill when continuing long-running roadmap work in the Termit repository after parity and core stabilization.

## Primary goals

1. Close open roadmap items in executable order (not just planning).
2. Keep the loop stable: `data -> train -> eval -> shadow -> promote`.
3. Improve orchestration quality with measurable KPIs and no silent regressions.
4. Preserve release discipline with CI gates and smoke checks.

## Execution mode

- Work in **do-all** style: implement, verify, and report facts.
- Prefer minimal diffs that extend existing architecture.
- Always continue from `.cursor/memory/ACTIVE.md` and current branch state.
- Do not stop on intermediate summaries while open tasks remain in `ACTIVE.md`; continue to the next actionable item in the same run.
- Escalate to the user only for true blockers (missing secrets/access, irreversible action approval, or forced product choice).

## Project memory (mandatory for new sessions)

- Treat `.cursor/memory/ACTIVE.md` as the canonical long-lived project memory for this template.
- Before each non-trivial task block:
  - read `.cursor/memory/ACTIVE.md`,
  - read the latest checkpoint in `.cursor/memory/checkpoints/` when available.
- After each meaningful implementation block:
  - append a short factual note to `## Сводка` (what changed and why),
  - add touched files to `## Файлы сессии`,
  - update `## Открытые задачи` with 1-3 next actionable items.
- Do not leave `## Открытые задачи` empty or placeholder-only after substantial work.
- In final response, include what memory was updated so the next session can continue without context loss.

## Focus order

1. Agent orchestration reliability and tool-loop execution quality.
2. Eval quality and strict release gates (model-bound, cloud judge where required).
3. Finetune improvements (SFT/DPO), regression gate, shadow rollout.
4. Ops observability and dashboard signals for decision-making.
5. Developer ergonomics (scripts, templates, automation toggles).

## Required checks after meaningful changes

1. Targeted unittest modules.
2. Full suite for wide changes: `.venv/bin/python -m unittest discover -s tests -q`
3. Runtime smoke: `./scripts/smoke_http.sh`

## Definition of done

- Feature is wired through `config -> state -> service -> route/schema -> tests`.
- KPIs/metrics exposed where relevant.
- No "please verify manually"; verification is executed in-session.
- Final summary includes passed/failed counts and HTTP status checks.
