# Runbook: падение Nightly flaky trend regression gate (первые 10 минут)

Короткий операционный чеклист для инцидента в CI job `nightly-quality-gates`, шаг:

- `Nightly flaky trend regression gate`

## 0-2 минуты: подтвердить причину падения

1. Откройте артефакт `flaky-watch-nightly`.
2. Проверьте файлы:
   - `flaky_watch_trend.md`
   - `flaky_watch_trend.json`
   - `flaky_watch_report.json`
3. Зафиксируйте:
   - какие suite помечены как `regressed`,
   - `pass_rate_delta` и `duration_mean_delta_seconds`,
   - `baseline_status` / `baseline_note` (важно для понимания, была ли корректная база сравнения).

### Troubleshooting: если `baseline_status != available`

- `missing` / `missing_payload`: baseline артефакт не найден или пустой, сравнение ограничено текущим nightly; ориентируйтесь на `flaky_watch_report.json` и локальное воспроизведение.
- `rate_limited` / `forbidden`: проблема доступа к GitHub API (`GITHUB_TOKEN`/лимиты), это инфраструктурный сигнал, а не сразу регресс тестов.
- `fetch_error` / `download_error`: временная ошибка загрузки baseline; проверьте стабильность сети/доступ к artifact API и повторите прогон.
- При любом не-`available` зафиксируйте это в статусе инцидента отдельно от вывода по самим suite.

### Как отличить product regression от infrastructure regression

- **Product regression:** есть воспроизводимый локальный провал suite/`pass_rate_delta < 0` при нормальном доступе к baseline (`baseline_status=available`).
- **Infrastructure regression:** проблемы в получении baseline (`rate_limited`, `forbidden`, `download_error`) или нестабильность окружения CI без устойчивого локального воспроизведения.
- **Смешанный случай:** сначала зафиксируйте инфраструктурный фактор, затем отдельно перепроверьте продуктовый сигнал повторным прогоном flaky-watch.

## Как читать flaky trend artifact (пример)

- `pass_rate_delta` показывает изменение доли успешных прогонов относительно baseline.
- Пример: у `tests.test_agents_api` было `pass_rate=1.0` (5/5), стало `pass_rate=0.8` (4/5), значит `pass_rate_delta=-0.2`.
- Для nightly gate это считается регрессом: отрицательный `pass_rate_delta` по critical suite должен запускать разбор причины и фиксацию (или короткий TTL override как временную меру).
- Грубая деградация: `pass_rate_delta=-1` означает фактический провал в ноль относительно baseline и требует немедленного разбора в первые 10 минут (без «отложим до завтра»).
- Временный override при `pass_rate_delta=-1` допустим только как экстренная мера на короткий TTL (обычно 24-72 часа) и только при подтверждённом инфраструктурном факторе; при подтверждённом продуктовой регрессии — недопустим, нужен немедленный фикс.

## 2-5 минут: быстрое воспроизведение локально

```bash
source .venv/bin/activate
python3 -m unittest tests.test_agents_api tests.test_platform_e2e -q
```

Если локально воспроизводится:

- это не transient флейк, переходите к фиксу.

Если локально не воспроизводится:

- запустите повторно 3-5 раз (через flaky-watch):

```bash
python3 scripts/flaky_watch_report.py \
  --suites tests.test_agents_api tests.test_platform_e2e \
  --iterations 5 \
  --output /tmp/flaky_watch_report_local.json \
  --markdown-output /tmp/flaky_watch_report_local.md
```

## 5-8 минут: решение по инциденту

### Вариант A (предпочтительно): быстрый фикс

- Исправьте источник регресса (код/тест/тайминг) и прогоните:
  - `python3 -m unittest discover -s tests -q`
  - `./scripts/smoke_http_core.sh`

### Вариант B (временная мера): TTL override

Если фикс не помещается в текущий слот, добавьте временный override:

Файл: `data/flaky_watch_gate_overrides.json`

```json
{
  "overrides": [
    {
      "suite": "tests.test_agents_api",
      "reason": "Incident hotfix pending (ticket ABC-123)",
      "expires_at": "2026-06-22T00:00:00Z"
    }
  ]
}
```

Правила:

- только для подтверждённых флейков;
- TTL 3-7 дней;
- максимум один активный override на один suite одновременно;
- продление override делайте отдельным коммитом (с обновлённым `reason`/`expires_at`);
- после фикса удалить override.

Подробно: `docs/FLAKY_WATCH_OVERRIDES_RU.md`.

### Когда НЕ использовать override (анти-паттерны)

- Когда регресс стабильно воспроизводится локально: это уже дефект, а не «временный флейк».
- Когда `expires_at` ставится «на месяц+» без плана исправления: это маскировка проблемы, а не контроль риска.
- Когда пытаются добавить override сразу для нескольких suite без отдельной диагностики по каждому.
- Когда override для `pass_rate_delta=-1` добавляется без инцидент-заметки с доказательством инфраструктурного фактора (`baseline_status`/API ошибки/лог деградации среды).

## 8-10 минут: коммуникация и контроль

1. Оставьте короткий статус в PR/канале:
   - affected suite,
   - root-cause (или гипотеза),
   - выбранное действие (fix/override),
   - срок удаления override (если использован).
2. Если добавлен override — обязательно создайте follow-up задачу на удаление до `expires_at`.
3. Проверка, что gate снова зелёный на следующем nightly прогоне.
4. Важно: для critical suite отрицательный `pass_rate_delta` (`< 0`) — блокер даже если поле `trend` в отчёте не равно `regressed`.
5. Если `pass_rate_delta` отсутствует или `null`, опирайтесь на `trend` и результат локального воспроизведения (это не автопропуск риска).
6. Допустимый тип `pass_rate_delta`: число или `null`; строки/булевы значения трактуются как невалидный сигнал и требуют проверки источника отчёта.
7. Приоритет правила: для critical suite отрицательный `pass_rate_delta` всегда важнее пустого/неопределённого `trend`.
8. `trend` сравнивается без учёта регистра: `ReGreSsEd` интерпретируется как `regressed` и считается регрессом.
9. Если `pass_rate_delta` пришёл строкой/булевым значением, сначала проверьте генератор trend-report (формат JSON полей), затем ретрайте gate.
10. Broad policy: при `fail_on_any_regression=True` gate падает по любому suite с `trend=regressed` (любой регистр) **или** с числовым `pass_rate_delta < 0`.
11. Исключение broad policy: если suite находится в активном override (не истёк `expires_at`), только этот конкретный suite не должен валить gate даже при `trend=regressed`/`pass_rate_delta < 0` (остальные suite проверяются в обычном режиме).

Короткий пример (один suite overridden, второй нет):
- `tests.test_agents_api`: `pass_rate_delta=-1`, есть активный override -> этот suite не валит gate.
- `tests.test_platform_e2e`: `trend=regressed`, override нет -> gate всё равно падает из-за этого suite.

### Что приложить к инциденту (минимум)

- Фрагмент из `flaky_watch_trend.md` по проблемному suite (`trend`, `pass_rate_delta`, `duration_mean_delta_seconds`).
- Значения `baseline_status` и `baseline_note` из nightly артефакта.
- Результат локального воспроизведения (`python3 -m unittest ...` или `flaky_watch_report.py` с числом итераций и итогом).
- Ссылка на PR/коммит с фиксом или запись override (`suite`, `reason`, `expires_at`).

Мини-чек JSON-ключей (из `flaky_watch_trend.json`) для инцидента:
`baseline_status`, `baseline_note`, `overall_trend`, `suites[].suite`, `suites[].trend`, `suites[].pass_rate_delta`, `suites[].duration_mean_delta_seconds`.

### Шаблон статуса в PR/чате

```text
Nightly flaky gate: <failed|passed_after_fix>
Suite: <tests.test_agents_api|tests.test_platform_e2e|...>
Signal: trend=<regressed|stable>, pass_rate_delta=<value>, baseline_status=<value>
Action: <fix merged | temporary override until YYYY-MM-DD>
```

### Когда запускать полный flaky-watch bundle

- Если инцидент не воспроизвелся с первого прогона или есть смешанный сигнал (`product` + `infrastructure`), прогоняйте полный пакет flaky-watch тестов:

```bash
python3 -m unittest tests.test_flaky_watch_report tests.test_flaky_watch_trend tests.test_flaky_watch_fetch_baseline tests.test_flaky_watch_gate -q
```

### Когда достаточно быстрого контура (только gate-тесты)

- Если меняли только `scripts/flaky_watch_gate.py` и/или тексты ошибок/валидации CLI, достаточно быстрого прогона:

```bash
python3 -m unittest tests.test_flaky_watch_gate -q
```

### Decision tree: быстрый контур vs полный bundle

- Меняли только логику `flaky_watch_gate.py`/его unit-тесты -> сначала быстрый контур (`tests.test_flaky_watch_gate`).
- Меняли логику тренда/репорта/загрузки baseline (`flaky_watch_trend.py`, `flaky_watch_report.py`, `flaky_watch_fetch_baseline.py`) -> сразу полный bundle.
- Если быстрый контур зелёный, но инцидент в nightly остаётся непонятным -> эскалируйте до полного bundle и сверяйте артефакты trend/report.

Мини-чек при fallback на full bundle:
- Зафиксируйте точную команду прогона и итоговый stdout (`Ran N tests`, `OK/FAILED`).
- Сохраните локальные артефакты flaky-watch (если запускали локальный report/trend): `/tmp/flaky_watch_report_local.json`, `/tmp/flaky_watch_report_local.md`.
- Сопоставьте локальный результат с nightly-артефактами `flaky_watch_trend.json` и `flaky_watch_report.json`.
