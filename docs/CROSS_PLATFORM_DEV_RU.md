# Кроссплатформенная разработка в Termit

Termit помогает собирать **приложения и игры** для **iOS, macOS, Windows и Android** через **атомарные шаги** — каждый шаг с отдельной проверкой, без монолитных PR на все платформы сразу.

## API

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/dev/cross-platform/stacks` | Список стеков (Flutter, Swift, Unity, …) |
| POST | `/api/dev/cross-platform/decompose` | Декомпозиция цели в atomic tasks + `first_step_prompt` |
| POST | `/api/dev/cross-platform/prepare` | Промпт для конкретного шага (`step_index`) |

Пример:

```bash
curl -s http://127.0.0.1:8765/api/dev/cross-platform/decompose \
  -H 'Content-Type: application/json' \
  -d '{"goal":"Flutter MVP для iOS и Android","stack_id":"flutter","platforms":["ios","android"]}'
```

## Шаблоны агентов

В [`data/agent_templates.json`](../data/agent_templates.json):

- `cross-platform-flutter`, `cross-platform-swift`, `cross-platform-android`
- `cross-platform-windows`, `cross-platform-maui`
- `game-unity`, `game-godot`

## Skill

[`data/skills/cross-platform-atomic/SKILL.md`](../data/skills/cross-platform-atomic/SKILL.md) — монтировать в agent run вместе с template.

## SDK (`@termit/client`)

```typescript
import { TermitClient, runAtomicDevWorkflow } from "@termit/client";

const client = new TermitClient({ workspace: "/path/to/app" });
const { plan, steps } = await runAtomicDevWorkflow(client, {
  goal: "Unity игра с pause menu для iOS и Android",
  stackId: "unity",
  agentId: "your-cross-platform-agent-id",
  onStep: (i, task) => console.log(i, task.title),
});
```

## Desktop

В чате — быстрые пресеты **Flutter**, **Swift**, **Unity**, **MAUI**: подставляют первый атомарный шаг и план.

## Eval

Сценарии `X1`–`X4` в [`data/eval_scenarios.json`](../data/eval_scenarios.json) (всего **53** сценария).

## Orchestrator

Задачи с ключевыми словами iOS/Android/Flutter/Unity/игра получают план `detect_stack_and_targets` + `atomic_*` шаги в `MultiAgentOrchestrator`.
