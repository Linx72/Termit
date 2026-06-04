# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-04T11:55:13Z

**Причина:** session stop

**Последний checkpoint:** [`20260604-115513_7ce5178a-ca97-4d9e-a7f1-.md`](checkpoints/20260604-115513_7ce5178a-ca97-4d9e-a7f1-.md)

## Сводка
- Если коротко: **Termit уже достаточно готов для практической разработки**, но пока не на уровне “100% без присмотра”. Оценка по состоянию сейчас: - **Готовность для MVP/обычных приложений:** ~**8/10** - **Готовность для production без контроля человека:** ~**6/10** Что уже хорош…
- Отличный вопрос. Чтобы он “поднимал” задачи качественно, нужно давать задачу в формате **ТЗ + критерии готовности**. Как ставить задачу в Termit (здесь): - Выберите агента `Website & App Builder Auto`. - Поставьте `execution mode = hybrid`. - Укажите `workspace` (куда писать фай…
- Да — **именно для этого**. `Termit Desktop` и делался как интерфейс, где агент: - принимает задачу “под ключ”, - сам планирует шаги, - пишет/меняет код в вашем workspace, - запускает проверки, - показывает ленту действий и изменения. То есть его цель — не просто чат, а **рабочий…
- Да, вы правы — в текущем состоянии это **не тот уровень автономности, который должен быть**. По факту сейчас проблема не в формулировке задач, а в рантайме выполнения: - run часто зависает после `skills_mounted`, - новые задачи остаются в `queued`, - из-за этого создаётся ощущен…
- Сделал `do all` и довёл до фактического результата. Исправил главную поломку, из-за которой очередь “замирала”: - В `app/services/agent_service.py` добавил fail-safe таймаут выполнения run в воркере: - `asyncio.wait_for(..., timeout=self._run_timeout_seconds)` - при таймауте run…
- Да, **может**, но с оговоркой по текущей стабильности. - Через `Termit Desktop` агент уже умеет работать в стиле Cursor: принять задачу, спланировать, создать/изменить файлы, запускать проверки и выдавать итог. - Для этого сейчас лучше использовать профиль **`Website & App Build…

## Файлы сессии
- `/Users/amoros/Projects/Termit/clients/termit-client/src/agent.ts`
- `/Users/amoros/Projects/Termit/clients/termit-client/src`
- `/Users/amoros/Projects/Termit/clients/termit-client/src/workflows.ts`
- `/Users/amoros/Projects/Termit/clients/termit-client/src/agentSse.ts`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/686741.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/341340.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/522604.txt`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/tsconfig.json`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/232011.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/922782.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/80233.txt`
- `/Users/amoros/Projects/Termit/app/services`
- `/Users/amoros/Projects/Termit/app/services/build_workflow_service.py`
- `/Users/amoros/Projects/Termit/README.md`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/src/index.css`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/src/PromptInputModal.tsx`
- `/Users/amoros/Projects/Termit/app/api/routes/agents.py`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/897013.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/986662.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/124161.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/376518.txt`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/753140.txt`
- `/Users/amoros/Projects/Termit/app/services/agent_run_queue.py`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/948640.txt`

## Открытые задачи
- [ ] Заполните вручную или через compact-chat после крупной сессии
