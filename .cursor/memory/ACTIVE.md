# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 (prod beta gate)

## Сводка
- **Prod beta gate:** `beta_prod_gate.sh` + workflow `beta-prod-gate.yml` (gate_mode=prod, D30+retention).
- **Staging smoke prod gate:** OK на :8080 (локальный hosted beta).
- **Learning loop:** preflight при `TERMIT_DPO_GPU_REQUIRED` или `TERMIT_LEARNING_LOOP_PREFLIGHT`.

## Открытые задачи
- [ ] Real GPU DPO → preflight OK → learning_loop_0423.sh
- [ ] Prod beta: secret `TERMIT_BETA_PROD_URL` + 5+ real desktop users
