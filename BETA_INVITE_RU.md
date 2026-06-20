# Beta invite — one page (RU)

Короткая ссылка для beta-тестеров Termit (локальный backend + Desktop).

## Ссылка для Desktop

После установки Termit.app откройте в браузере или из терминала:

```text
file:///path/to/Termit/clients/termit-desktop/index.html#beta-onboard
```

Или запустите dev-сервер desktop и откройте:

```text
http://localhost:5173/#beta-onboard
```

**Хэши:**

| Hash | Действие |
|------|----------|
| `#beta` | Открыть панель настроек, прокрутка к Beta feedback |
| `#beta-onboard` | То же + wizard первого запуска (onboarding) |

## 5 минут для тестера

1. Клонировать репозиторий, `./scripts/do_all_setup.sh`
2. `./scripts/upgrade_model_ladder_phase_a.sh` (или `ollama pull qwen2.5-coder:14b` + recreate `termit-core-ft`)
3. API: `http://127.0.0.1:8765/health` → `ok`
4. Desktop: `cd clients/termit-desktop && npm run dev` → `#beta-onboard`
5. API key (если auth): `viewer-key` из `.env.example`
6. Отправить feedback в панели Beta — попадает в `data/feedback.jsonl`

## Hosted beta (опционально)

```bash
./scripts/deploy_hosted_beta.sh
# invite URL:
http://127.0.0.1:8080/#beta-onboard
```

## Что просим от beta

- 3–5 agent runs (coding) с tool loop
- Один composer + verify
- Feedback (rating + текст) в UI
- Возврат через 7 и 30 дней (для D30 retention gate)

Подробнее: [`BETA_ONBOARDING.md`](BETA_ONBOARDING.md), [`HOSTED_DEPLOYMENT.md`](HOSTED_DEPLOYMENT.md).
