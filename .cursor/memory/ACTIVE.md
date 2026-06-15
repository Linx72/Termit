# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-15 (roadmap wave 2 — закрытие)

## Сводка
- Roadmap `termit_model_roadmap_73860914.plan.md` — инфраструктура закрыта; release gate ждёт quality uplift.
- **426 тестов OK** (skipped=1): routing, adapter dedup, shadow routing, regression gate.
- Live smoke (2026-06-15): `/health` 200, `/api/eval/dashboard` 200 (99 scenarios), `run-suite/fast` 200 (12/12), `run-suite/deep` 200 (52/53, 98.1%), `run-suite/release` **412** (quality_median 2.5 < 3.0), `teacher-distill` 200.

## Wave 1–2 (готово)
- Stage1 recover/export, Modelfile `termit-core-ft`, weekly schedule
- Eval 3.0: IQ/SWE/HumanEval, rubric judge, benchmark API, tier gates
- Autonomy: `outcome_class`, agent loop stop-conditions
- `LlmCallerService`, `ReasoningOrchestratorService`, 3-tier routing (fast/code/frontier)
- `cloud_teacher` не в `teacher_model_ids`; adapter dedup on promote
- Shadow/promote: `TERMIT_FINETUNE_SHADOW_TRAFFIC_PERCENT`, `_upsert_repo_profile_shadow`, `RoutingPolicyService._pick_profile_model` — покрыто тестами
- Teacher distill: сначала `LlmCallerService` если provider доступен; offline fallback при отсутствии provider или ошибке вызова (локально без API key)

## Файлы (ключевые)
- `app/services/llm_caller_service.py`, `reasoning_orchestrator_service.py`, `model_router.py`
- `app/core/model_roles.py`, `app/api/routes/finetune.py`
- `app/services/finetune_service.py`, `routing_policy_service.py`, `finetune_trainer_service.py`
- `tests/test_routing_policy_service.py`, `test_finetune_service.py`, `test_model_router.py`
- `.env.example` — QLoRA GPU hint

## Открытые блокеры
- [ ] **Release eval gate**: quality_median 2.5 при пороге 3.0 — нужен cloud judge или улучшение heuristic/cloud `TERMIT_EVAL_QUALITY_JUDGE_MODEL`
- [ ] **Реальный QLoRA/GGUF**: GPU + `TERMIT_FINETUNE_TRAINER=hf`, `TERMIT_FINETUNE_HF_DRY_RUN=false`, unsloth
- [ ] **Cloud teacher live**: `OPENAI_COMPAT_BASE_URL` есть, `OPENAI_COMPAT_API_KEY` пуст — distillation может идти через offline fallback
