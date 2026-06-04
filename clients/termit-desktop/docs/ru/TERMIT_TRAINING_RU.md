# Termit — программа обучения

Версия: 0.3.2  
Формат: пошаговые модули (≈ 2–3 часа суммарно)

---

## Модуль 0. Введение (15 мин)

**Цель:** понять архитектуру Termit.

1. Прочитайте справку TERMIT_HELP_RU.pdf (раздел 1).
2. Убедитесь: API `:8765`, Ollama, desktop Connect — всё зелёное.
3. Выберите workspace с небольшим Python/JS проектом.

**Критерий успеха:** health OK, workspace выбран.

---

## Модуль 1. Первый Chat run (20 мин)

**Цель:** streaming chat с контекстом.

1. Вкладка **Chat** → прикрепите `@ файл` из workspace.
2. Запрос: «Объясни структуру этого файла и предложи один улучшающий refactor».
3. Включите retrieval (@codebase) в sidebar.
4. Сохраните сессию (Sessions → Новая / переименование).

**Критерий успеха:** ответ ссылается на ваш файл, streaming без обрыва.

---

## Модуль 2. Composer и apply (25 мин)

**Цель:** безопасное редактирование кода.

1. Вкладка **Composer** → Add file → опишите маленькую правку (unit-test, docstring).
2. Изучите diff preview и **Safe apply** hint.
3. **Apply** одного hunk → проверьте файл в **Editor**.
4. Вкладка **Terminal** → `python3 -m unittest …` или `npm test`.

**Критерий успеха:** patch применён, verify команда выполнена.

---

## Модуль 3. Plan mode (15 мин)

**Цель:** планирование без немедленного кода.

1. Вкладка **Plan** → задача: «Добавить endpoint /api/example».
2. Получите план (без patch).
3. **Build → Composer** — перенос плана в composer draft.
4. Выполните apply из модуля 2.

**Критерий успеха:** plan → composer → apply цепочка пройдена.

---

## Модуль 4. Agent tool loop (30 мин)

**Цель:** автономный агент с tools.

1. Вкладка **Agents** → выберите agent (например coding agent).
2. Включите **Авто-запуск агента** в sidebar.
3. North Star → **«Локальная фича end-to-end»** → **Запустить агентом**.
4. Наблюдайте timeline: list_files, read_file, apply_patch, verify.
5. При confirm — подтвердите write operation.

**Критерий успеха:** run state = completed, verify passed.

---

## Модуль 5. North Star и Atomic (20 мин)

**Цель:** готовые сценарии и cross-platform.

1. Пройдите сценарий **Agent autopilot** (resume при сбое).
2. Chat → preset chip → draft для Flutter/React preset.
3. **▶ Atomic (auto agent)** — полный atomic workflow с verify gates.

**Критерий успеха:** atomic workflow завершён или корректно остановлен на verify.

---

## Модуль 6. Quality и eval (20 мин)

**Цель:** KPI, eval gate, observability.

1. Sidebar: KPI gate, Agent observability panels.
2. Online → **Run eval heavy job** (если API доступен).
3. `curl http://127.0.0.1:8765/api/metrics/executive-summary?days=1`
4. Сравните pass rate с порогом TERMIT_EVAL_MIN_PASS_RATE.

**Критерий успеха:** понимаете pass_rate и tool loop metrics.

---

## Модуль 7. Автоматизация (15 мин)

**Цель:** hands-off режим.

1. `./scripts/do_all_automatic.sh` (или уже установлено).
2. Проверьте LaunchAgent, Stage1 scheduler status API.
3. Weekly eval crontab (Mon 04:00) — опционально.

**Критерий успеха:** scheduler enabled, smoke HTTP 200.

---

## Итоговый проект

**Задание:** реализуйте маленькую фичу end-to-end только через Termit:

1. Plan → Composer → apply → terminal verify → agent run для polish.
2. Зафиксируйте git diff.
3. Запишите: TTFUC (time to first useful commit), pass verify, agent steps count.

**Сертификат самопроверки:** все 7 модулей + итоговый проект выполнены.

---

## Дополнительные материалы

- TERMIT_HELP_RU.pdf — полная справка
- START_HERE_RU.md в репозитории
- Eval сценарии: `data/eval_scenarios.json`

Обучение доступно офлайн через вкладку **Справка** в desktop Termit.
