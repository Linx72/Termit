"""Конфигурация pytest для Termit.

Фикс Python 3.14: `asyncio.Runner.run()` падает с RuntimeError
при кумулятивном загрязнении thread-local `_running_loop`.
Решение: вызов C-функции `_set_running_loop(None)` перед каждым тестом
для принудительного сброса thread-local состояния.

Безопасно: _set_running_loop — приватное API asyncio (Python 3.7+),
используется только для очистки в тестовом окружении.
"""

import asyncio.events
import gc

import pytest


def _reset_running_loop() -> None:
    """Сбросить thread-local _running_loop через C-API asyncio."""
    try:
        asyncio.events._set_running_loop(None)
    except Exception:
        pass
    gc.collect()


@pytest.fixture(autouse=True)
def _clean_event_loop() -> None:
    """Очистка thread-local event loop перед и после каждого теста."""
    _reset_running_loop()
    yield
    _reset_running_loop()
