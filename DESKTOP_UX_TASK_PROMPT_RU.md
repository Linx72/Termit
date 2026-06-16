# Termit — промпт: Desktop UX, i18n и agent modes

> **Назначение:** мастер-промпт для агентов при правках Termit Desktop, SectionGuide, переводе UI, Guided/Autopilot, policy presets.
>
> **Skills:** [`.cursor/skills/termit-desktop/SKILL.md`](file:///Users/amoros/Projects/Termit/.cursor/skills/termit-desktop/SKILL.md), [`.cursor/skills/termit-prompts/SKILL.md`](file:///Users/amoros/Projects/Termit/.cursor/skills/termit-prompts/SKILL.md)
>
> **Platform skill:** [`data/skills/termit-desktop/SKILL.md`](file:///Users/amoros/Projects/Termit/data/skills/termit-desktop/SKILL.md)

---

## Северная звезда

Пользователь открывает **Termit.app** и сразу понимает **зачем каждая вкладка** и **как ею пользоваться** — на русском по умолчанию. Агенты запускаются в режиме **Guided** (с confirm) или **Autopilot** (без пауз на risky tools).

---

## Карта вкладок (Desktop)

| Вкладка | Зачем | Типичный поток |
|---------|-------|----------------|
| Чат | Диалог + @контекст | Connect → @файл → Send |
| Компоновщик | Мультифайловые патчи | @files → Run → Apply all |
| Редактор | Monaco + inline AI | Открыть файл → правка |
| План | План без кода | Plan → Build → Composer |
| Терминал | Shell через API | git status / pytest |
| Задачи | Очередь tasks | Queue from chat |
| Агенты | Tool loop | Run → Confirm/Resume |
| Онлайн | Share + heavy jobs | hybrid mode |
| Задания | Brief-проекты | Create → seed agent |
| Справка | PDF локально | Help / Training |

Примечание по режимам чата (Cursor-like):
- `Agent` -> `run_mode=agent`
- `Ask` -> `run_mode=ask` (server-enforced read-only tools)
- `Plan` -> `run_mode=plan` (plan-only run, затем Build -> Composer)
- `Terminal` -> запуск quick/suggested команд через TerminalPanel

Тексты блоков: `clients/termit-desktop/src/i18n.ts` (`sg*Title`, `sg*Purpose`, `sg*Steps`).

### Единый UI-поток (desktop + web)

- Выбор файлов/папок (`Open file`, `@file`, `@folder`, `Composer @file`) — через `WorkspaceFilePickerModal`.
- Короткие вводы (`@symbol`, `@web`, path inputs) — через `PromptInputModal`.
- Не использовать `window.prompt` и platform-specific picker ветки в core UX.
- `runtimeMode` (`auto|desktop|web`) использовать для server-control семантики, а не для расхождения UI-поведения.

---

## Guided vs Autopilot

| | Guided | Autopilot |
|---|--------|-----------|
| UI | sidebar «Режим агента» | Autopilot |
| Preset | solo / team / strict | autopilot |
| Confirm | да | нет (auto) |
| Verify after patch | по preset | да |
| Prompt | `data/prompts/desktop-guided-agent.md` | `data/prompts/desktop-autopilot-agent.md` |
| Skill | `agent-guided` | `agent-autopilot` |

Backend: `data/desktop_policy_presets.json`, `AgentPolicyPresetService.apply_to_run()`, `_invoke_loop_tool` + `auto_confirm_risky_tools`.

---

## Задачи агента (чеклист)

### UI / перевод

- [x] Все строки через `t(locale, key)` — ключи в **ru и en**
- [x] SectionGuide на каждой вкладке + sidebar
- [x] Режимы `Ask/Plan/Agent/Terminal` отображаются в toolbar/badges и соответствуют backend `run_mode`
- [x] Cursor-like поток `termit-prompts`: `Plan` в селекторе чата -> `Build -> Composer` / `Build -> Composer -> Verify` без ручного `window.prompt`
- [x] `npm run build` в `clients/termit-desktop`
- [x] `./scripts/package_desktop.sh`

### Новый промпт / skill

- [x] `data/prompts/<name>.md` (desktop-guided, desktop-autopilot, …)
- [x] `data/skills/<id>/SKILL.md` (frontmatter name + description)
- [x] Запись в `data/agent_templates.json` с `skill_ids`
- [x] `python3 -m unittest tests.test_platform_parity -q`

---

## Файлы

| Что | Путь |
|-----|------|
| i18n | `clients/termit-desktop/src/i18n.ts` |
| SectionGuide | `clients/termit-desktop/src/SectionGuide.tsx` |
| App | `clients/termit-desktop/src/App.tsx` |
| Unified file picker | `clients/termit-desktop/src/WorkspaceFilePickerModal.tsx` |
| Unified input modal | `clients/termit-desktop/src/PromptInputModal.tsx` |
| Presets | `data/desktop_policy_presets.json` |
| Prompts | `data/prompts/*.md` |
| Skills | `data/skills/*/SKILL.md` |
| Templates | `data/agent_templates.json` |

---

## Verify

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -q
python3 -m unittest tests.test_desktop_runtime_mode_smoke -q
cd clients/termit-desktop && npm run build
./scripts/package_desktop.sh
curl -s http://127.0.0.1:8765/api/desktop/policy-presets | python3 -m json.tool
```

Ответ пользователю — **на русском**, с фактическим passed/failed.
