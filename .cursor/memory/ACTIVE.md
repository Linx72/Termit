# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-07-01 — тесты: 765 passed, 0 failed (фикс Python 3.14 event loop leak)

## Сводка
- **Тесты:** 27 pre-existing failures исправлены одним фиксом в `tests/conftest.py`
- **Корень:** Python 3.14 `asyncio.Runner.run()` падает с `RuntimeError: Runner.run() cannot be called from a running event loop` при кумулятивном загрязнении thread-local `_running_loop`
- **Решение:** `asyncio.events._set_running_loop(None)` — C-функция сброса thread-local — вызывается перед/после каждого теста
- **Результат:** 765 passed, 6 skipped, 0 failed

## Файлы
- `tests/conftest.py` — создан: 43 строки, `_reset_running_loop()` + `autouse` fixture

## Открытые задачи
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO (нужен адрес GPU-сервера)
- [ ] `TERMIT_BETA_PROD_URL` + real desktop users (нужен URL продакшена)
- [x] `OPENAI_COMPAT_API_KEY` в GitHub Secrets ✅ (установлен 2026-06-29)
