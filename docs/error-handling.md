# Система обработки ошибок TermitPro

> P0-аудит и модернизация · 2026-07-01 · `f59f656`

## Архитектура

```
┌─────────────────── Exception ─────────────────────────────────────────────┐
│                                                                           │
│ 1. domain/exceptions.py ─── Таксономия                                    │
│    ├─ TermitError           (базовый, error_category + is_recoverable)    │
│    ├─ ProviderError         (LLM-провайдеры: 401, 429, 5xx)              │
│    ├─ ValidationError       (входные данные: Prompt, JSON, Config)        │
│    ├─ CircuitBreakerOpen    (схема сработала)                             │
│    ├─ RateLimited           (превышена квота)                             │
│    ├─ AuthenticationError   (неверный токен, JWT)                         │
│    ├─ ResourceNotFound      (404)                                         │
│    ├─ ConfigurationError    (неверный конфиг)                             │
│    ├─ InternalError         (непредвиденное, 500)                         │
│    ├─ TimeoutError          (превышен таймаут)                            │
│    └─ ExternalServiceError  (отказ внешнего сервиса)                      │
│                                                                           │
│ 2. middleware/error_handler.py ─── HTTP-интеграция                        │
│    • Перехватывает ВСЕ unhandled exceptions (ASGI middleware)              │
│    • Форматирует JSON: {error, detail, category, recoverable, trace_id}   │
│    • Маскирует длинные traceback'и (max 2000 символов)                    │
│    • Логирует каждую ошибку с trace_id                                    │
│                                                                           │
│ 3. services/guardrail_service.py ─── Guardrail (C1)                       │
│    • Валидация промптов перед отправкой к LLM                             │
│    • 7 паттернов секретов (re.compile)                                    │
│    • Проверка допустимых символов, PUA/U+FFFD                             │
│    • Проверка длины промпта                                               │
│    • ENABLE_GUARDRAIL в config (default: true)                            │
│                                                                           │
│ 4. services/provider_circuit_breaker.py ─── Circuit Breaker               │
│    • Per-provider protection: Empty → CLOSED → OPEN                       │
│    • Cooldown: provider_circuit_breaker_cooldown_seconds                  │
│    • Threshold: circuit_failure_threshold (в config)                      │
│    • Встроен в chat_service.py в 4 точках (stream, retry, fallback)       │
│    • Авто-восстановление после cooldown                                   │
│                                                                           │
│ 5. api/routes/health.py ─── Health-check                                  │
│    • GET /health — статус (healthy/degraded) + CB-состояния               │
│    • GET /health/circuit-breakers — per-provider CB-состояния             │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

## Таксономия ошибок

| Класс | HTTP | category | recoverable | Причина |
|-------|:----:|----------|:-----------:|--------|
| `TermitError` | 500 | `internal` | ❌ | Базовый (не используется напрямую) |
| `ProviderError` | 502 | `provider` | ✅ | 401/429/5xx от LLM-провайдера |
| `ValidationError` | 400 | `validation` | ❌ | Неверный prompt/JSON/config |
| `CircuitBreakerOpen` | 503 | `circuit_breaker` | ✅ | Схема разомкнута из-за накопленных ошибок |
| `RateLimited` | 429 | `rate_limit` | ✅ | Превышена квота запросов |
| `AuthenticationError` | 401 | `authentication` | ❌ | Неверный токен/JWT |
| `ResourceNotFound` | 404 | `not_found` | ❌ | Ресурс не найден |
| `ConfigurationError` | 500 | `configuration` | ❌ | Неверный конфиг |
| `InternalError` | 500 | `internal` | ❌ | Непредвиденная ошибка |
| `TimeoutError` | 504 | `timeout` | ✅ | Таймаут операции |
| `ExternalServiceError` | 502 | `external_service` | ✅ | Отказ внешнего сервиса |

## Как добавлять новые ошибки

```python
# 1. ДОБАВИТЬ КЛАСС в app/domain/exceptions.py
class PaymentError(TermitError):
    """Ошибка платёжного шлюза."""
    error_category = "payment"
    is_recoverable = True

# 2. ДОБАВИТЬ МАППИНГИ в функции в том же файле:
#    - _CATEGORY_FALLBACK (для get_error_category)
#    - _HTTP_STATUS_FALLBACK (для get_http_status)
#    - _RECOVERABLE_FALLBACK (для get_is_recoverable)

# 3. HTTP-ответ автоматический через ErrorHandlerMiddleware
#    JSON: {"error": "payment_error", "detail": "...", 
#            "category": "payment", "recoverable": true, "trace_id": "a1b2c3d4"}
```

## Circuit Breaker workflow

```
Empty ─── первый ошибка ──→ CLOSED ─── N ошибок (threshold) ──→ OPEN ────┐
  ↑                              ↑                                       │
  └── холодный старт              │                                       │
                                 │                                       │
                             успешный вызов                              │
                             остаётся CLOSED                            cooldown
                                                                         │
                              ┌──────────────────────────────────────────┘
                              ↓
                            HALF-OPEN ─── успех ──→ CLOSED
                              │
                              └── ошибка ──→ OPEN (сброс cooldown)
```

**Конфиг (config.py):**
- `circuit_failure_threshold: int = 5` — ошибок до размыкания
- `provider_circuit_breaker_cooldown_seconds: int = 30` — время до восстановления
- `provider_retry_backoff_base_ms: int = 1000` — база для экспоненциального backoff

## Guardrail: проверка промптов

```
Промпт → check_prompt() → ValidationError?
                           ├─ Да → HTTP 400 + подробности
                           └─ Нет → продолжение в chat flow
```

**Проверки:**
1. Секреты: API ключи (sk-*), токены (Bearer), пароли
2. Управляющие символы (\x00-\x08, \x0b-\x0c, \x0e-\x1f)
3. PUA/U+FFFD (замена символов)
4. Длина промпта (max_prompt_length в config)

## Интеграция с chat_service.py

```python
# Точка 1: validate (guardrail)
await guardrail_service.check_prompt(user_prompt)   # → ValidationError или OK

# Точка 2-4: provider calls (circuit breaker)
try:
    cb.before_call("deepseek")                       # → CircuitBreakerOpen или OK
    response = await provider_api.call(...)
    cb.on_success("deepseek")                        # → CLOSED
except Exception:
    cb.on_failure("deepseek")                        # → проверка threshold
    raise
```

## Тесты

| Файл | Тестов | Что покрыто |
|------|:------:|-------------|
| `test_agent_loop_errors.py` | 8 | Интеграция E1 в agent loop |
| `test_error_handler.py` | 9 | HTTP-ответы, категории, маскирование traceback |
| `test_guardrail_service.py` | 10 | Валидация промптов (секреты, символы, длина) |
| `test_provider_circuit_breaker.py` | 8 | Жизненный цикл CB: Empty→CLOSED→OPEN→CLOSED |
| **Всего** | **35** | |

Запуск всех тестов:
```bash
pytest tests/ -q --tb=short
```

## Конфигурация

Все пороги в `app/core/config.py`:

```python
# Guardrail
ENABLE_GUARDRAIL: bool = True
max_prompt_length: int = 32000

# Circuit breaker
circuit_failure_threshold: int = 5
provider_circuit_breaker_cooldown_seconds: int = 30

# Retry
provider_retry_backoff_base_ms: int = 1000
```

## Эндпоинты

| Endpoint | Метод | Назначение |
|----------|:-----:|------------|
| `/health` | GET | Статус (healthy/degraded) + CB-состояния |
| `/health/circuit-breakers` | GET | Per-provider CB-состояния |

## Принятые решения

1. **Не трогаем бизнес-логику LLM** — только инфраструктура обработки ошибок
2. **JSON-логи с redaction** — секреты маскируются автоматически
3. **Обратная совместимость событий** — tool_loop_* события не изменены
4. **Пороги в config, не хардкод** — все тюнингуемые параметры вынесены
5. **Circuit breaker per-provider** — изоляция провайдеров друг от друга
6. **Health-check через GET /health** — без аутентификации
