# Termit — веб-приложения (Vite / React)

## Быстрый старт (всё одной командой)

```bash
cd ~/Projects/Termit
./scripts/do_all_web_apps.sh
```

Или по шагам:

1. API: `./scripts/restart_server.sh`
2. Desktop: `./scripts/run_termit_stack.sh` → **Terminal** (npm dev/test/build) · **Задания** (assignments)
3. Агенты: `./scripts/seed_web_agents.sh` или кнопки на вкладке **Задания**
4. Шаблон **`web-app-vite`**, skill **`web-app`** (`allow_online` уже в JSON)

## Шаблон и промпт

| Ресурс | Путь |
|--------|------|
| Шаблон агента | `web-app-vite` в `data/agent_templates.json` |
| Skill | `data/skills/web-app/SKILL.md` |
| System prompt | `data/prompts/web-app-builder.md` |

## Verify после патча

Termit автоматически подбирает команду:

- Python-репо → `unittest`
- `package.json` → `npm test` + `npm run lint` + `npm run build` (если есть в scripts)

Проверка: `GET /api/tools/workspace-scripts`

## Онлайн + UI

- `allow_online=true` + `browser_navigate` на `http://localhost:5173` после `npm run dev`
- Skill `online-project` для заданий с deliverables

## Eval

Сценарий **F1** — React form (task runner).

## Cursor

Skill: `.cursor/skills/web-app/SKILL.md`
