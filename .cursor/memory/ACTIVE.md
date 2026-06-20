# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 (extended release gate + docs)

## Сводка
- **release_gate_local extended:** OK (~229s, 691 tests)
- **release_smoke:** confirm_run regression в core + reset patch fixture
- **CHANGELOG / RELEASE_FLOW:** задокументированы фиксы

## Открытые задачи
- [ ] Real GPU DPO → preflight OK → learning_loop_0423.sh
- [ ] Prod beta: secret `TERMIT_BETA_PROD_URL` + 5+ real desktop users
- [x] beta-prod-gate.yml — fix secrets в if (41981e2)
- [x] RELEASE_CHECKLIST + RELEASE_FLOW — confirm_run / patch fixture
