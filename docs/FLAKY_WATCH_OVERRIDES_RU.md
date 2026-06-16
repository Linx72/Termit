# Flaky Watch Overrides (Nightly)

Краткая инструкция для временных исключений в nightly gate `flaky_watch_gate.py`.

## Где настраивается

- Файл конфигурации: `data/flaky_watch_gate_overrides.json`
- Используется в CI job `nightly-quality-gates`, шаг `Nightly flaky trend regression gate`.
- Оперативный runbook (первые 10 минут): `docs/NIGHTLY_FLAKY_GATE_RUNBOOK_RU.md`
- В CLI `scripts/flaky_watch_gate.py` аргумент `--overrides` должен указывать на JSON-файл (если путь — директория, overrides будут проигнорированы).

## Формат

```json
{
  "overrides": [
    {
      "suite": "tests.test_agents_api",
      "reason": "Known flake after dependency update",
      "expires_at": "2026-06-22T00:00:00Z"
    }
  ]
}
```

Поля:

- `suite` — имя unittest suite (например, `tests.test_platform_e2e`).
- `reason` — короткая причина, зачем временно разрешён регресс.
- `expires_at` — срок действия override (UTC, ISO8601, рекомендуется `...Z`).

## TTL-политика

- Override всегда должен иметь `expires_at`.
- Рекомендуемый TTL: 3-7 дней.
- После истечения `expires_at` override автоматически перестаёт применяться.
- Если проблема не решена к дате истечения, продление делайте отдельным коммитом с обновлённым `reason`.

## Правила использования

- Добавляйте override только для известных, воспроизводимых флейков.
- Не используйте override как постоянный обход quality gate.
- Для критичных suite (`tests.test_agents_api`, `tests.test_platform_e2e`) override допускается только как краткосрочная мера.
- После фикса флейка удаляйте запись из `overrides`.
- При инциденте действуйте по runbook: `docs/NIGHTLY_FLAKY_GATE_RUNBOOK_RU.md`.

## Типовые ошибки конфигурации overrides

- В `--overrides` передан путь к директории вместо JSON-файла (в этом случае overrides не применяются).
- JSON синтаксически невалиден (gate завершится с ошибкой `Invalid overrides JSON: ...`).
- Временный override добавлен без `expires_at` — такая запись не активируется и не снимет регресс в gate.
