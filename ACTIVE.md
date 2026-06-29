# Termit — Active Tasks & Done Log

## Completed (29.06.2026)

### Bug Fixes
- **test_ten_tasks_complete_and_expose_events** — исправлен: `read_readme` handler
  больше не падает при отсутствии README.md (task_service.py:384-389).
  Fix: системный — ToolingError в read_readme теперь возвращает grace-заметку
  вместо VerificationError.
  ---
  724 passed, 6 skipped, 0 failed.

- **test_tool_loop_metrics_recent_window** — исправлен: хардкод даты заменён
  на `datetime.now(timezone.utc) - timedelta(days=1)`.

### Infrastructure
- **OPENAI_COMPAT_API_KEY** — установлен в GitHub Secrets (repo: Linx72/Termit).
- **Deploy (prod 8082)** — сервер перезапущен с новым кодом, health OK.

### Servers Running
- Dev: 8765 (PID 30986) — health OK
- Prod: 8082 (PID 51035) — health OK, AuthQuotaMiddleware active
