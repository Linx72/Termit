# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-21 — full `do_all_automatic` + hosted smoke OK

## Сводка
- **do_all_automatic** + dev green: exit 0 (~69s).
- **Hosted smoke** `http://127.0.0.1:8080` — OK.
- **726 unittest** — OK.
- Automation + skill auto-select on; API :8765 up.

## Файлы сессии (skills)
- `app/services/skill_store.py`, `skill_selector_service.py`, `agent_service.py`, `agent_tool_schema.py`
- `app/api/routes/projects.py`, `app/domain/schemas.py`, `app/core/config.py`
- `data/skills/termit-agent`, `termit-automation`, `termit-prompts` (runtime)
- `scripts/sync_cursor_skills.sh`
- `clients/termit-client/`, `clients/termit-desktop/` (UI + SDK)
- `tests/test_skill_store.py`, `test_skill_selector.py`, `test_platform_parity.py`

## Открытые задачи
- [ ] `OPENAI_COMPAT_API_KEY` в `.env` + GitHub Secrets
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
- [ ] `TERMIT_BETA_PROD_URL` + real desktop users
