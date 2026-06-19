# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-19T09:55:00Z

## Сводка

- Colima запущен, **hosted beta** на `:8080` — smoke OK
- Ollama warm on startup + `POST /api/local/models/warm`
- Chat KPI: rolling `chat_latency_p95_recent_ms` (окно 50)
- Agent run success gate (пред. коммит)

## Открытые задачи (фаза 5)

- [ ] GPU + cloud API key
- [ ] Beta cohort ≥5
- [ ] Product KPI gates green
