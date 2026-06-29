# Termit Active Tasks — 30.06.2026

## Выполнено
- ✅ **test_ten_tasks_complete_and_expose_events** — read_readme handler исправлен: отсутствие README.md = предупреждение, не VerifError
- ✅ **ACTIVE.md** — создан заново
- ✅ **Отключены быстрые ответы** — model_router.py: fast_model удалён из low-complexity tier, все coding-задачи → code_model
- ✅ **724 теста проходят**, 0 фейлов
- ✅ **Пуш на GitHub** — 19 файлов, коммит 99703f8
- ✅ **Деплой** — dev (8765) и prod (8082) перезапущены, health OK

## Сервера
- Dev: 127.0.0.1:8765 — PID 54744
- Prod: 127.0.0.1:8082 — PID 54776
- TermitPro backend: 8646 — работает (отдельный процесс из .app)
- Hermes dashboard: 18765 — OK

## Осталось
- TermitPro приложение — обновить SwiftUI (если нужно синхронизировать fast_model логику на клиенте)

## Файлы
- 18 изменённых + ACTIVE.md (новый)
