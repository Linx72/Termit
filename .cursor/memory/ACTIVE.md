# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-19T07:15:00Z

**Причина:** do all прогон

## Сводка (последний do all)

```bash
TERMIT_SKIP_OLLAMA_CHECK=1 TERMIT_DO_ALL_PLAN=true ./scripts/do_all_automatic.sh
```

| Проверка | Результат |
|----------|-----------|
| Итог | **exit 0**, ~111 с |
| verify_ci + plan | OK |
| Hosted smoke `:8080` | **пропущен** (docker down) |
| `automatic_mode_enabled` | **true** |
| Finetune KPI | **failed** delta=0% |
| `overall_ok` | **false** (5 warnings) |

## Открытые задачи (фаза 5)

- [ ] Docker + deploy_hosted_beta
- [ ] GPU, cloud key, beta ≥5, product KPI
