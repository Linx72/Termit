from dataclasses import dataclass, field
import os
from typing import Dict

from dotenv import load_dotenv

from app.core.api_key_config import ApiKeyConfig

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_api_keys(
    value: str,
    default_daily_quota: int,
    default_role: str = "operator",
) -> Dict[str, ApiKeyConfig]:
    keys: Dict[str, ApiKeyConfig] = {}
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        segments = item.split(":")
        if len(segments) == 1:
            keys[segments[0].strip()] = ApiKeyConfig(
                daily_quota=default_daily_quota,
                role=default_role,
            )
        elif len(segments) == 2:
            keys[segments[0].strip()] = ApiKeyConfig(
                daily_quota=int(segments[1].strip()),
                role=default_role,
            )
        elif len(segments) == 3:
            keys[segments[0].strip()] = ApiKeyConfig(
                daily_quota=int(segments[1].strip()),
                role=segments[2].strip(),
            )
        else:
            keys[segments[0].strip()] = ApiKeyConfig(
                daily_quota=int(segments[1].strip()),
                role=segments[2].strip(),
                team=segments[3].strip(),
            )
    return keys


def _parse_team_quotas(value: str) -> Dict[str, int]:
    quotas: Dict[str, int] = {}
    for part in value.split(","):
        item = part.strip()
        if not item or ":" not in item:
            continue
        team, limit = item.split(":", 1)
        team_name = team.strip()
        if not team_name:
            continue
        quotas[team_name] = int(limit.strip())
    return quotas


def _parse_clamped_float_env(key: str, default: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    raw = os.getenv(key, str(default))
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: list[str]
    default_model: str
    code_model: str
    analysis_model: str
    default_fallback_model: str
    code_fallback_model: str
    analysis_fallback_model: str
    ollama_base_url: str
    openai_compat_base_url: str
    openai_compat_api_key: str
    memory_backend: str
    memory_sqlite_path: str
    memory_max_messages: int
    auth_enabled: bool
    api_keys: Dict[str, ApiKeyConfig]
    quota_sqlite_path: str
    default_daily_quota: int
    default_api_role: str
    feedback_file_path: str
    circuit_failure_threshold: int
    circuit_cooldown_seconds: int
    eval_scenarios_path: str
    task_backend: str
    task_sqlite_path: str
    teacher_model: str = "ollama:deepseek-coder"
    teacher_fallback_model: str = "openai_compat:deepseek-ai/deepseek-coder-33b-instruct"
    agent_run_backend: str = "sqlite"
    agent_run_sqlite_path: str = "./termit_agent_runs.db"
    agent_registry_file_path: str = "./data/agents.json"
    agent_max_concurrency: int = 2
    agent_max_queue_size: int = 100
    agent_run_max_attempts: int = 2
    agent_run_retry_backoff_ms: int = 250
    agent_run_timeout_seconds: int = 180
    agent_queue_stuck_timeout_seconds: int = 120
    agent_shutdown_grace_seconds: int = 30
    agent_run_max_events_per_run: int = 500
    agent_run_max_response_chars: int = 12000
    agent_run_retention_days: int = 14
    agent_memory_sqlite_path: str = "./termit_agent_memory.db"
    agent_memory_max_entries: int = 50
    agent_eval_scenarios_path: str = "./data/agent_eval_scenarios.json"
    agent_verify_after_patch: bool = True
    agent_auto_confirm_risky: bool = False
    agent_verify_cmd: str = "python3 -m unittest discover -s tests -q"
    agent_verify_max_retries: int = 1
    dual_pass_enabled: bool = True
    dual_pass_task_types: str = "coding,review,debug"
    task_use_agent: bool = False
    task_agent_id: str = ""
    fim_max_tokens: int = 64
    agent_maintenance_enabled: bool = True
    agent_cleanup_interval_seconds: int = 3600
    agent_metrics_snapshot_interval_seconds: int = 900
    agent_stale_run_timeout_seconds: int = 7200
    response_cache_backend: str = "memory"
    response_cache_sqlite_path: str = "./termit_response_cache.db"
    response_cache_ttl_seconds: int = 120
    telemetry_max_latency_points: int = 5000
    metrics_snapshot_file_path: str = "./data/metrics_snapshots.jsonl"
    eval_report_file_path: str = "./data/eval_reports.jsonl"
    orchestration_eval_report_file_path: str = "./data/orchestration_eval_reports.jsonl"
    eval_min_pass_rate: float = 0.95
    eval_ci_limit: int = 53
    eval_iq_scenarios_path: str = "./data/eval_scenarios_iq.json"
    eval_swe_scenarios_path: str = "./data/eval_scenarios_swe.json"
    eval_humaneval_scenarios_path: str = "./data/eval_scenarios_humaneval.json"
    eval_quality_judge_model: str = ""
    eval_benchmark_reference_model: str = "openai_compat:deepseek-ai/DeepSeek-V3"
    cloud_teacher_model: str = "openai_compat:deepseek-ai/DeepSeek-V3"
    fast_model: str = "ollama:qwen2.5-coder"
    frontier_fallback_model: str = "openai_compat:deepseek-ai/DeepSeek-V3"
    reasoning_draft_model: str = ""
    reasoning_critic_model: str = ""
    orchestration_openhands_contract_enabled: bool = False
    orchestration_tool_loop_execution_enabled: bool = False
    finetune_pipeline_stuck_timeout_seconds: int = 3600
    retrieval_enabled: bool = True
    retrieval_mode: str = "semantic"
    retrieval_auto_reindex: bool = True
    retrieval_root_path: str = "."
    retrieval_embed_model: str = "nomic-embed-text"
    retrieval_embed_cache_path: str = "./data/retrieval_embeddings.db"
    retrieval_max_chunks: int = 6
    retrieval_chunk_max_chars: int = 1200
    retrieval_max_file_bytes: int = 200000
    context_max_messages: int = 20
    context_max_chars: int = 12000
    context_summary_max_chars: int = 2000
    context_enrichment_enabled: bool = True
    repo_map_max_dirs: int = 40
    project_rules_dir: str = "./data/projects"
    agent_templates_path: str = "./data/agent_templates.json"
    provider_retry_attempts: int = 2
    provider_retry_backoff_ms: int = 150
    degrade_empty_response_rate: float = 0.05
    degrade_fallback_rate: float = 0.35
    agent_alert_queue_utilization_percent: float = 80.0
    agent_alert_dead_letter_rate: float = 0.15
    agent_alert_min_worker_alive_ratio: float = 1.0
    agent_alert_min_verify_pass_rate: float = 0.70
    team_quotas: Dict[str, int] = field(default_factory=dict)
    repo_model_profiles_path: str = "./data/repo_model_profiles.json"
    routing_benchmarks_path: str = "./data/routing_benchmarks.json"
    finetune_datasets_dir: str = "./data/finetune/datasets"
    finetune_jobs_path: str = "./data/finetune/jobs.json"
    finetune_adapters_path: str = "./data/finetune/adapters.json"
    finetune_pipelines_path: str = "./data/finetune/pipelines.json"
    finetune_cycle_events_path: str = "./data/finetune/stage1_cycle_events.jsonl"
    finetune_pipeline_max_concurrency: int = 1
    stage1_schedule_enabled: bool = False
    stage1_schedule_weekday: int = 0
    stage1_schedule_hour: int = 3
    stage1_schedule_minute: int = 0
    stage1_schedule_name: str = "weekly-stage1"
    stage1_schedule_base_model: str = ""
    stage1_schedule_min_samples: int = 10
    stage1_schedule_run_eval_baseline: bool = True
    stage1_schedule_eval_limit: int = 24
    stage1_schedule_auto_register_adapter: bool = False
    stage1_schedule_state_path: str = "./data/finetune/schedule_state.json"
    finetune_auto_train: bool = False
    finetune_trainer: str = "ollama"
    finetune_ollama_bin: str = "ollama"
    finetune_output_model: str = "termit-core-ft"
    finetune_auto_register_after_train: bool = False
    finetune_modelfiles_dir: str = "./data/finetune/modelfiles"
    finetune_adapters_dir: str = "./data/finetune/adapters"
    finetune_train_timeout_seconds: int = 600
    finetune_hf_dry_run: bool = True
    finetune_hf_epochs: int = 1
    finetune_hf_lora_rank: int = 16
    finetune_hf_max_samples: int = 500
    finetune_hf_auto_gguf: bool = True
    finetune_hf_auto_ollama: bool = False
    finetune_llama_cpp_path: str = ""
    finetune_patch_outcomes_path: str = "./data/finetune/patch_outcomes.jsonl"
    finetune_capture_patch_reverts: bool = True
    finetune_training_signals_path: str = "./data/finetune/training_signals.jsonl"
    finetune_auto_capture_signals: bool = True
    finetune_min_signal_output_chars: int = 32
    finetune_auto_post_eval: bool = True
    finetune_repo_profile_id: str = "termit-core"
    finetune_regression_gate_enabled: bool = True
    finetune_regression_require_post_eval: bool = True
    finetune_min_signals_for_train: int = 50
    finetune_max_train_regression: float = 0.05
    finetune_shadow_traffic_percent: float = 10.0
    auto_start_ollama: bool = False
    routing_max_candidates: int = 4
    routing_cost_aware_enabled: bool = False
    routing_model_costs: str = ""
    routing_default_openai_cost_usd: float = 0.002
    routing_default_ollama_cost_usd: float = 0.0
    alert_webhook_url: str = ""
    skills_dir: str = "./data/skills"
    hooks_config_path: str = "./data/hooks/hooks.json"
    hooks_webhook_url: str = ""
    hooks_enabled: bool = True
    automation_webhook_secret: str = ""
    guardrails_enabled: bool = True
    guardrails_max_patch_chars: int = 50000
    trace_spans_db_path: str = "./termit_trace_spans.db"
    search_api_url: str = "http://127.0.0.1:8888"
    search_api_key: str = ""
    search_provider: str = "searxng"
    browser_backend: str = "httpx"
    assignments_dir: str = "./data/assignments"
    mcp_registry_path: str = "./data/mcp_servers.json"
    desktop_state_dir: str = "./data/desktop"
    desktop_north_star_path: str = "./data/desktop_north_star.json"
    desktop_policy_presets_path: str = "./data/desktop_policy_presets.json"
    agent_schedules_db_path: str = "./termit_agent_schedules.db"
    agent_schedules_enabled: bool = True
    agent_schedules_poll_seconds: int = 60
    daily_improvement_enabled: bool = False
    daily_improvement_hour: int = 2
    daily_improvement_minute: int = 0
    daily_improvement_agent_id: str = ""
    daily_improvement_max_agent_runs: int = 3
    daily_improvement_max_dlq_replay: int = 2
    daily_improvement_max_eval_fixes: int = 2
    daily_improvement_eval_probe_limit: int = 12
    daily_improvement_run_eval_probe: bool = True
    daily_improvement_auto_create_agent: bool = True
    daily_improvement_state_path: str = "./data/ops/daily_improvement_state.json"
    skill_auto_select_enabled: bool = True
    skill_auto_select_max: int = 3
    skill_auto_select_min_score: float = 3.0
    media_enabled: bool = False
    media_storage: str = "./data/media"
    media_max_cost_usd: float = 25.0
    media_confirm_cost_usd: float = 1.0
    media_image_provider: str = "openai"
    media_image_model: str = "dall-e-3"
    media_image_cost_usd: float = 0.08
    media_tts_cost_usd: float = 0.015
    media_transcribe_cost_usd: float = 0.006
    media_tts_voice: str = "alloy"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    fal_api_key: str = ""
    media_jobs_db_path: str = "./data/media/media_jobs.db"
    media_i2v_provider: str = "stub"
    media_i2v_cost_usd: float = 0.50
    media_brand_kits_dir: str = "./data/media/brand_kits"
    media_eval_scenarios_path: str = "./data/eval_scenarios_media.json"
    openai_api_key: str = ""
    openai_api_base_url: str = "https://api.openai.com/v1"


def get_settings() -> Settings:
    return Settings(
        host=os.getenv("TERMIT_HOST", "0.0.0.0"),
        port=int(os.getenv("TERMIT_PORT", "8765")),
        allowed_origins=_split_csv(os.getenv("TERMIT_ALLOWED_ORIGINS", "*")),
        default_model=os.getenv("TERMIT_DEFAULT_MODEL", "ollama:termit-core-ft"),
        code_model=os.getenv("TERMIT_CODE_MODEL", "ollama:termit-core-ft"),
        analysis_model=os.getenv("TERMIT_ANALYSIS_MODEL", "ollama:termit-core-ft"),
        default_fallback_model=os.getenv(
            "TERMIT_DEFAULT_FALLBACK_MODEL",
            "ollama:qwen2.5-coder",
        ),
        code_fallback_model=os.getenv(
            "TERMIT_CODE_FALLBACK_MODEL",
            "ollama:qwen2.5-coder",
        ),
        analysis_fallback_model=os.getenv(
            "TERMIT_ANALYSIS_FALLBACK_MODEL",
            "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
        ),
        teacher_model=os.getenv("TERMIT_TEACHER_MODEL", "ollama:deepseek-coder"),
        teacher_fallback_model=os.getenv(
            "TERMIT_TEACHER_FALLBACK_MODEL",
            "openai_compat:deepseek-ai/deepseek-coder-33b-instruct",
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        openai_compat_base_url=os.getenv("OPENAI_COMPAT_BASE_URL", "http://localhost:8001"),
        openai_compat_api_key=os.getenv("OPENAI_COMPAT_API_KEY", ""),
        memory_backend=os.getenv("TERMIT_MEMORY_BACKEND", "sqlite"),
        memory_sqlite_path=os.getenv("TERMIT_MEMORY_SQLITE_PATH", "./termit_memory.db"),
        memory_max_messages=int(os.getenv("TERMIT_MEMORY_MAX_MESSAGES", "40")),
        auth_enabled=os.getenv("TERMIT_AUTH_ENABLED", "false").lower() in {"1", "true", "yes"},
        api_keys=_parse_api_keys(
            os.getenv("TERMIT_API_KEYS", ""),
            int(os.getenv("TERMIT_DEFAULT_DAILY_QUOTA", "1000")),
            default_role=os.getenv("TERMIT_DEFAULT_API_ROLE", "operator"),
        ),
        quota_sqlite_path=os.getenv("TERMIT_QUOTA_SQLITE_PATH", "./termit_quota.db"),
        default_daily_quota=int(os.getenv("TERMIT_DEFAULT_DAILY_QUOTA", "1000")),
        default_api_role=os.getenv("TERMIT_DEFAULT_API_ROLE", "operator"),
        feedback_file_path=os.getenv("TERMIT_FEEDBACK_FILE", "./data/feedback.jsonl"),
        circuit_failure_threshold=int(os.getenv("TERMIT_CIRCUIT_FAILURE_THRESHOLD", "3")),
        circuit_cooldown_seconds=int(os.getenv("TERMIT_CIRCUIT_COOLDOWN_SECONDS", "60")),
        eval_scenarios_path=os.getenv("TERMIT_EVAL_SCENARIOS_PATH", "./data/eval_scenarios.json"),
        task_backend=os.getenv("TERMIT_TASK_BACKEND", "sqlite"),
        task_sqlite_path=os.getenv("TERMIT_TASK_SQLITE_PATH", "./termit_tasks.db"),
        agent_run_backend=os.getenv("TERMIT_AGENT_RUN_BACKEND", "sqlite"),
        agent_run_sqlite_path=os.getenv("TERMIT_AGENT_RUN_SQLITE_PATH", "./termit_agent_runs.db"),
        agent_registry_file_path=os.getenv("TERMIT_AGENT_REGISTRY_FILE", "./data/agents.json"),
        agent_max_concurrency=int(os.getenv("TERMIT_AGENT_MAX_CONCURRENCY", "2")),
        agent_max_queue_size=int(os.getenv("TERMIT_AGENT_MAX_QUEUE_SIZE", "100")),
        agent_run_max_attempts=int(os.getenv("TERMIT_AGENT_RUN_MAX_ATTEMPTS", "2")),
        agent_run_retry_backoff_ms=int(os.getenv("TERMIT_AGENT_RUN_RETRY_BACKOFF_MS", "250")),
        agent_run_timeout_seconds=max(3, int(os.getenv("TERMIT_AGENT_RUN_TIMEOUT_SECONDS", "180"))),
        agent_queue_stuck_timeout_seconds=max(
            10,
            int(os.getenv("TERMIT_AGENT_QUEUE_STUCK_TIMEOUT_SECONDS", "120")),
        ),
        agent_shutdown_grace_seconds=max(
            0,
            int(os.getenv("TERMIT_AGENT_SHUTDOWN_GRACE_SECONDS", "30")),
        ),
        agent_run_max_events_per_run=int(os.getenv("TERMIT_AGENT_RUN_MAX_EVENTS_PER_RUN", "500")),
        agent_run_max_response_chars=int(os.getenv("TERMIT_AGENT_RUN_MAX_RESPONSE_CHARS", "12000")),
        agent_run_retention_days=int(os.getenv("TERMIT_AGENT_RUN_RETENTION_DAYS", "14")),
        agent_memory_sqlite_path=os.getenv(
            "TERMIT_AGENT_MEMORY_SQLITE_PATH",
            "./termit_agent_memory.db",
        ),
        agent_memory_max_entries=int(os.getenv("TERMIT_AGENT_MEMORY_MAX_ENTRIES", "50")),
        agent_eval_scenarios_path=os.getenv(
            "TERMIT_AGENT_EVAL_SCENARIOS_PATH",
            "./data/agent_eval_scenarios.json",
        ),
        agent_verify_after_patch=os.getenv("TERMIT_AGENT_VERIFY_AFTER_PATCH", "true").lower()
        in {"1", "true", "yes"},
        agent_auto_confirm_risky=os.getenv("TERMIT_AGENT_AUTO_CONFIRM_RISKY", "false").lower()
        in {"1", "true", "yes"},
        agent_verify_cmd=os.getenv(
            "TERMIT_AGENT_VERIFY_CMD",
            "python3 -m unittest discover -s tests -q",
        ),
        agent_verify_max_retries=max(0, int(os.getenv("TERMIT_AGENT_VERIFY_MAX_RETRIES", "1"))),
        dual_pass_enabled=os.getenv("TERMIT_DUAL_PASS_ENABLED", "true").lower() in {"1", "true", "yes"},
        dual_pass_task_types=os.getenv(
            "TERMIT_DUAL_PASS_TASK_TYPES",
            "coding,review,debug",
        ),
        task_use_agent=os.getenv("TERMIT_TASK_USE_AGENT", "false").lower() in {"1", "true", "yes"},
        task_agent_id=os.getenv("TERMIT_TASK_AGENT_ID", ""),
        fim_max_tokens=int(os.getenv("TERMIT_FIM_MAX_TOKENS", "64")),
        agent_maintenance_enabled=os.getenv("TERMIT_AGENT_MAINTENANCE_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        agent_cleanup_interval_seconds=int(os.getenv("TERMIT_AGENT_CLEANUP_INTERVAL_SECONDS", "3600")),
        agent_metrics_snapshot_interval_seconds=int(
            os.getenv("TERMIT_AGENT_METRICS_SNAPSHOT_INTERVAL_SECONDS", "900")
        ),
        agent_stale_run_timeout_seconds=int(
            os.getenv("TERMIT_AGENT_STALE_RUN_TIMEOUT_SECONDS", "7200")
        ),
        response_cache_backend=os.getenv("TERMIT_RESPONSE_CACHE_BACKEND", "memory"),
        response_cache_sqlite_path=os.getenv(
            "TERMIT_RESPONSE_CACHE_SQLITE_PATH",
            "./termit_response_cache.db",
        ),
        response_cache_ttl_seconds=int(os.getenv("TERMIT_RESPONSE_CACHE_TTL_SECONDS", "120")),
        telemetry_max_latency_points=int(os.getenv("TERMIT_TELEMETRY_MAX_LATENCY_POINTS", "5000")),
        metrics_snapshot_file_path=os.getenv(
            "TERMIT_METRICS_SNAPSHOT_FILE",
            "./data/metrics_snapshots.jsonl",
        ),
        eval_report_file_path=os.getenv("TERMIT_EVAL_REPORT_FILE", "./data/eval_reports.jsonl"),
        orchestration_eval_report_file_path=os.getenv(
            "TERMIT_ORCH_EVAL_REPORT_FILE",
            "./data/orchestration_eval_reports.jsonl",
        ),
        eval_min_pass_rate=_parse_clamped_float_env("TERMIT_EVAL_MIN_PASS_RATE", 0.95),
        eval_ci_limit=int(os.getenv("TERMIT_EVAL_CI_LIMIT", "53")),
        eval_iq_scenarios_path=os.getenv(
            "TERMIT_EVAL_IQ_SCENARIOS_PATH", "./data/eval_scenarios_iq.json"
        ),
        eval_swe_scenarios_path=os.getenv(
            "TERMIT_EVAL_SWE_SCENARIOS_PATH", "./data/eval_scenarios_swe.json"
        ),
        eval_humaneval_scenarios_path=os.getenv(
            "TERMIT_EVAL_HUMANEVAL_SCENARIOS_PATH", "./data/eval_scenarios_humaneval.json"
        ),
        eval_quality_judge_model=os.getenv("TERMIT_EVAL_QUALITY_JUDGE_MODEL", ""),
        eval_benchmark_reference_model=os.getenv(
            "TERMIT_EVAL_BENCHMARK_REFERENCE_MODEL",
            "openai_compat:deepseek-ai/DeepSeek-V3",
        ),
        cloud_teacher_model=os.getenv(
            "TERMIT_CLOUD_TEACHER_MODEL",
            "openai_compat:deepseek-ai/DeepSeek-V3",
        ),
        fast_model=os.getenv("TERMIT_FAST_MODEL", "ollama:qwen2.5-coder"),
        frontier_fallback_model=os.getenv(
            "TERMIT_FRONTIER_FALLBACK_MODEL",
            "openai_compat:deepseek-ai/DeepSeek-V3",
        ),
        reasoning_draft_model=os.getenv("TERMIT_REASONING_DRAFT_MODEL", ""),
        reasoning_critic_model=os.getenv("TERMIT_REASONING_CRITIC_MODEL", ""),
        orchestration_openhands_contract_enabled=os.getenv(
            "TERMIT_ORCH_OPENHANDS_CONTRACT_ENABLED",
            "false",
        ).lower()
        in {"1", "true", "yes"},
        orchestration_tool_loop_execution_enabled=os.getenv(
            "TERMIT_ORCH_TOOL_LOOP_EXECUTION_ENABLED",
            "false",
        ).lower()
        in {"1", "true", "yes"},
        finetune_pipeline_stuck_timeout_seconds=max(
            60, int(os.getenv("TERMIT_FINETUNE_PIPELINE_STUCK_TIMEOUT_SECONDS", "3600"))
        ),
        retrieval_enabled=os.getenv("TERMIT_RETRIEVAL_ENABLED", "true").lower() in {"1", "true", "yes"},
        retrieval_mode=os.getenv("TERMIT_RETRIEVAL_MODE", "semantic"),
        retrieval_auto_reindex=os.getenv("TERMIT_RETRIEVAL_AUTO_REINDEX", "true").lower()
        in {"1", "true", "yes"},
        retrieval_root_path=os.getenv("TERMIT_RETRIEVAL_ROOT_PATH", "."),
        retrieval_embed_model=os.getenv("TERMIT_RETRIEVAL_EMBED_MODEL", "nomic-embed-text"),
        retrieval_embed_cache_path=os.getenv(
            "TERMIT_RETRIEVAL_EMBED_CACHE_PATH",
            "./data/retrieval_embeddings.db",
        ),
        retrieval_max_chunks=int(os.getenv("TERMIT_RETRIEVAL_MAX_CHUNKS", "6")),
        retrieval_chunk_max_chars=int(os.getenv("TERMIT_RETRIEVAL_CHUNK_MAX_CHARS", "1200")),
        retrieval_max_file_bytes=int(os.getenv("TERMIT_RETRIEVAL_MAX_FILE_BYTES", "200000")),
        context_max_messages=int(os.getenv("TERMIT_CONTEXT_MAX_MESSAGES", "20")),
        context_max_chars=int(os.getenv("TERMIT_CONTEXT_MAX_CHARS", "12000")),
        context_summary_max_chars=int(os.getenv("TERMIT_CONTEXT_SUMMARY_MAX_CHARS", "2000")),
        context_enrichment_enabled=os.getenv("TERMIT_CONTEXT_ENRICHMENT_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        repo_map_max_dirs=int(os.getenv("TERMIT_REPO_MAP_MAX_DIRS", "40")),
        project_rules_dir=os.getenv("TERMIT_PROJECT_RULES_DIR", "./data/projects"),
        agent_templates_path=os.getenv("TERMIT_AGENT_TEMPLATES_PATH", "./data/agent_templates.json"),
        provider_retry_attempts=int(os.getenv("TERMIT_PROVIDER_RETRY_ATTEMPTS", "2")),
        provider_retry_backoff_ms=int(os.getenv("TERMIT_PROVIDER_RETRY_BACKOFF_MS", "150")),
        degrade_empty_response_rate=_parse_clamped_float_env("TERMIT_DEGRADE_EMPTY_RATE", 0.05),
        degrade_fallback_rate=_parse_clamped_float_env("TERMIT_DEGRADE_FALLBACK_RATE", 0.35),
        agent_alert_queue_utilization_percent=_parse_clamped_float_env(
            "TERMIT_AGENT_ALERT_QUEUE_UTILIZATION_PERCENT",
            80.0,
            min_value=1.0,
            max_value=100.0,
        ),
        agent_alert_dead_letter_rate=_parse_clamped_float_env(
            "TERMIT_AGENT_ALERT_DEAD_LETTER_RATE",
            0.15,
        ),
        agent_alert_min_worker_alive_ratio=_parse_clamped_float_env(
            "TERMIT_AGENT_ALERT_MIN_WORKER_ALIVE_RATIO",
            1.0,
        ),
        agent_alert_min_verify_pass_rate=_parse_clamped_float_env(
            "TERMIT_AGENT_ALERT_MIN_VERIFY_PASS_RATE",
            0.70,
        ),
        team_quotas=_parse_team_quotas(os.getenv("TERMIT_TEAM_QUOTAS", "")),
        repo_model_profiles_path=os.getenv(
            "TERMIT_REPO_MODEL_PROFILES_PATH",
            "./data/repo_model_profiles.json",
        ),
        routing_benchmarks_path=os.getenv(
            "TERMIT_ROUTING_BENCHMARKS_PATH",
            "./data/routing_benchmarks.json",
        ),
        finetune_datasets_dir=os.getenv(
            "TERMIT_FINETUNE_DATASETS_DIR",
            "./data/finetune/datasets",
        ),
        finetune_jobs_path=os.getenv("TERMIT_FINETUNE_JOBS_PATH", "./data/finetune/jobs.json"),
        finetune_adapters_path=os.getenv(
            "TERMIT_FINETUNE_ADAPTERS_PATH",
            "./data/finetune/adapters.json",
        ),
        finetune_pipelines_path=os.getenv(
            "TERMIT_FINETUNE_PIPELINES_PATH",
            "./data/finetune/pipelines.json",
        ),
        finetune_cycle_events_path=os.getenv(
            "TERMIT_FINETUNE_CYCLE_EVENTS_PATH",
            "./data/finetune/stage1_cycle_events.jsonl",
        ),
        finetune_pipeline_max_concurrency=max(
            1,
            int(os.getenv("TERMIT_FINETUNE_PIPELINE_MAX_CONCURRENCY", "1")),
        ),
        stage1_schedule_enabled=os.getenv("TERMIT_STAGE1_SCHEDULE_ENABLED", "false").lower()
        in {"1", "true", "yes"},
        stage1_schedule_weekday=max(0, min(int(os.getenv("TERMIT_STAGE1_SCHEDULE_WEEKDAY", "0")), 6)),
        stage1_schedule_hour=max(0, min(int(os.getenv("TERMIT_STAGE1_SCHEDULE_HOUR", "3")), 23)),
        stage1_schedule_minute=max(0, min(int(os.getenv("TERMIT_STAGE1_SCHEDULE_MINUTE", "0")), 59)),
        stage1_schedule_name=os.getenv("TERMIT_STAGE1_SCHEDULE_NAME", "weekly-stage1"),
        stage1_schedule_base_model=os.getenv("TERMIT_STAGE1_SCHEDULE_BASE_MODEL", ""),
        stage1_schedule_min_samples=max(
            1,
            int(os.getenv("TERMIT_STAGE1_SCHEDULE_MIN_SAMPLES", "10")),
        ),
        stage1_schedule_run_eval_baseline=os.getenv(
            "TERMIT_STAGE1_SCHEDULE_RUN_EVAL_BASELINE",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        stage1_schedule_eval_limit=max(
            1,
            min(int(os.getenv("TERMIT_STAGE1_SCHEDULE_EVAL_LIMIT", "24")), 100),
        ),
        stage1_schedule_auto_register_adapter=os.getenv(
            "TERMIT_STAGE1_SCHEDULE_AUTO_REGISTER_ADAPTER",
            "false",
        ).lower()
        in {"1", "true", "yes"},
        stage1_schedule_state_path=os.getenv(
            "TERMIT_STAGE1_SCHEDULE_STATE_PATH",
            "./data/finetune/schedule_state.json",
        ),
        finetune_auto_train=os.getenv("TERMIT_FINETUNE_AUTO_TRAIN", "false").lower()
        in {"1", "true", "yes"},
        finetune_trainer=os.getenv("TERMIT_FINETUNE_TRAINER", "ollama"),
        finetune_ollama_bin=os.getenv("TERMIT_FINETUNE_OLLAMA_BIN", "ollama"),
        finetune_output_model=os.getenv("TERMIT_FINETUNE_OUTPUT_MODEL", "termit-core-ft"),
        finetune_auto_register_after_train=os.getenv(
            "TERMIT_FINETUNE_AUTO_REGISTER_AFTER_TRAIN",
            "false",
        ).lower()
        in {"1", "true", "yes"},
        finetune_modelfiles_dir=os.getenv(
            "TERMIT_FINETUNE_MODELFILES_DIR",
            "./data/finetune/modelfiles",
        ),
        finetune_adapters_dir=os.getenv(
            "TERMIT_FINETUNE_ADAPTERS_DIR",
            "./data/finetune/adapters",
        ),
        finetune_train_timeout_seconds=max(
            30,
            int(os.getenv("TERMIT_FINETUNE_TRAIN_TIMEOUT_SECONDS", "600")),
        ),
        finetune_hf_dry_run=os.getenv("TERMIT_FINETUNE_HF_DRY_RUN", "true").lower()
        in {"1", "true", "yes"},
        finetune_hf_epochs=max(1, int(os.getenv("TERMIT_FINETUNE_HF_EPOCHS", "1"))),
        finetune_hf_lora_rank=max(4, int(os.getenv("TERMIT_FINETUNE_HF_LORA_RANK", "16"))),
        finetune_hf_max_samples=max(
            1,
            int(os.getenv("TERMIT_FINETUNE_HF_MAX_SAMPLES", "500")),
        ),
        finetune_hf_auto_gguf=os.getenv("TERMIT_FINETUNE_HF_AUTO_GGUF", "true").lower()
        in {"1", "true", "yes"},
        finetune_hf_auto_ollama=os.getenv("TERMIT_FINETUNE_HF_AUTO_OLLAMA", "false").lower()
        in {"1", "true", "yes"},
        finetune_llama_cpp_path=os.getenv("TERMIT_FINETUNE_LLAMA_CPP_PATH", ""),
        finetune_patch_outcomes_path=os.getenv(
            "TERMIT_FINETUNE_PATCH_OUTCOMES_PATH",
            "./data/finetune/patch_outcomes.jsonl",
        ),
        finetune_capture_patch_reverts=os.getenv(
            "TERMIT_FINETUNE_CAPTURE_PATCH_REVERTS",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        finetune_training_signals_path=os.getenv(
            "TERMIT_FINETUNE_TRAINING_SIGNALS_PATH",
            "./data/finetune/training_signals.jsonl",
        ),
        finetune_auto_capture_signals=os.getenv(
            "TERMIT_FINETUNE_AUTO_CAPTURE_SIGNALS",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        finetune_min_signal_output_chars=max(
            8,
            int(os.getenv("TERMIT_FINETUNE_MIN_SIGNAL_OUTPUT_CHARS", "32")),
        ),
        finetune_auto_post_eval=os.getenv("TERMIT_FINETUNE_AUTO_POST_EVAL", "true").lower()
        in {"1", "true", "yes"},
        finetune_repo_profile_id=os.getenv("TERMIT_FINETUNE_REPO_PROFILE_ID", "termit-core"),
        finetune_regression_gate_enabled=os.getenv(
            "TERMIT_FINETUNE_REGRESSION_GATE_ENABLED",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        finetune_regression_require_post_eval=os.getenv(
            "TERMIT_FINETUNE_REGRESSION_REQUIRE_POST_EVAL",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        finetune_min_signals_for_train=max(
            1,
            int(os.getenv("TERMIT_FINETUNE_MIN_SIGNALS_FOR_TRAIN", "50")),
        ),
        finetune_max_train_regression=max(
            0.0,
            float(os.getenv("TERMIT_FINETUNE_MAX_TRAIN_REGRESSION", "0.05")),
        ),
        finetune_shadow_traffic_percent=max(
            0.0,
            min(float(os.getenv("TERMIT_FINETUNE_SHADOW_TRAFFIC_PERCENT", "10")), 100.0),
        ),
        auto_start_ollama=os.getenv("TERMIT_AUTO_START_OLLAMA", "false").lower()
        in {"1", "true", "yes", "on"},
        alert_webhook_url=os.getenv("TERMIT_ALERT_WEBHOOK_URL", ""),
        routing_max_candidates=int(os.getenv("TERMIT_ROUTING_MAX_CANDIDATES", "4")),
        routing_cost_aware_enabled=os.getenv("TERMIT_ROUTING_COST_AWARE_ENABLED", "false").lower()
        in {"1", "true", "yes"},
        routing_model_costs=os.getenv("TERMIT_ROUTING_MODEL_COSTS", ""),
        routing_default_openai_cost_usd=max(
            0.0,
            float(os.getenv("TERMIT_ROUTING_DEFAULT_OPENAI_COST_USD", "0.002")),
        ),
        routing_default_ollama_cost_usd=max(
            0.0,
            float(os.getenv("TERMIT_ROUTING_DEFAULT_OLLAMA_COST_USD", "0.0")),
        ),
        skills_dir=os.getenv("TERMIT_SKILLS_DIR", "./data/skills"),
        hooks_config_path=os.getenv("TERMIT_HOOKS_CONFIG_PATH", "./data/hooks/hooks.json"),
        hooks_webhook_url=os.getenv("TERMIT_HOOKS_WEBHOOK_URL", ""),
        hooks_enabled=os.getenv("TERMIT_HOOKS_ENABLED", "true").lower() in {"1", "true", "yes"},
        automation_webhook_secret=os.getenv("TERMIT_AUTOMATION_WEBHOOK_SECRET", ""),
        guardrails_enabled=os.getenv("TERMIT_GUARDRAILS_ENABLED", "true").lower() in {"1", "true", "yes"},
        guardrails_max_patch_chars=int(os.getenv("TERMIT_GUARDRAILS_MAX_PATCH_CHARS", "50000")),
        trace_spans_db_path=os.getenv("TERMIT_TRACE_SPANS_DB_PATH", "./termit_trace_spans.db"),
        search_api_url=os.getenv("TERMIT_SEARCH_API_URL", "http://127.0.0.1:8888"),
        search_api_key=os.getenv("TERMIT_SEARCH_API_KEY", ""),
        search_provider=os.getenv("TERMIT_SEARCH_PROVIDER", "searxng"),
        browser_backend=os.getenv("TERMIT_BROWSER_BACKEND", "httpx").strip().lower(),
        assignments_dir=os.getenv("TERMIT_ASSIGNMENTS_DIR", "./data/assignments"),
        mcp_registry_path=os.getenv("TERMIT_MCP_REGISTRY_PATH", "./data/mcp_servers.json"),
        desktop_state_dir=os.getenv("TERMIT_DESKTOP_STATE_DIR", "./data/desktop"),
        desktop_north_star_path=os.getenv(
            "TERMIT_DESKTOP_NORTH_STAR_PATH",
            "./data/desktop_north_star.json",
        ),
        desktop_policy_presets_path=os.getenv(
            "TERMIT_DESKTOP_POLICY_PRESETS_PATH",
            "./data/desktop_policy_presets.json",
        ),
        agent_schedules_db_path=os.getenv(
            "TERMIT_AGENT_SCHEDULES_DB_PATH",
            "./termit_agent_schedules.db",
        ),
        agent_schedules_enabled=os.getenv("TERMIT_AGENT_SCHEDULES_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        agent_schedules_poll_seconds=int(os.getenv("TERMIT_AGENT_SCHEDULES_POLL_SECONDS", "60")),
        daily_improvement_enabled=os.getenv("TERMIT_DAILY_IMPROVEMENT_ENABLED", "false").lower()
        in {"1", "true", "yes"},
        daily_improvement_hour=max(0, min(int(os.getenv("TERMIT_DAILY_IMPROVEMENT_HOUR", "2")), 23)),
        daily_improvement_minute=max(
            0,
            min(int(os.getenv("TERMIT_DAILY_IMPROVEMENT_MINUTE", "0")), 59),
        ),
        daily_improvement_agent_id=os.getenv("TERMIT_DAILY_IMPROVEMENT_AGENT_ID", ""),
        daily_improvement_max_agent_runs=max(
            1,
            int(os.getenv("TERMIT_DAILY_IMPROVEMENT_MAX_AGENT_RUNS", "3")),
        ),
        daily_improvement_max_dlq_replay=max(
            0,
            int(os.getenv("TERMIT_DAILY_IMPROVEMENT_MAX_DLQ_REPLAY", "2")),
        ),
        daily_improvement_max_eval_fixes=max(
            0,
            int(os.getenv("TERMIT_DAILY_IMPROVEMENT_MAX_EVAL_FIXES", "2")),
        ),
        daily_improvement_eval_probe_limit=max(
            1,
            min(int(os.getenv("TERMIT_DAILY_IMPROVEMENT_EVAL_PROBE_LIMIT", "12")), 53),
        ),
        daily_improvement_run_eval_probe=os.getenv(
            "TERMIT_DAILY_IMPROVEMENT_RUN_EVAL_PROBE",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        daily_improvement_auto_create_agent=os.getenv(
            "TERMIT_DAILY_IMPROVEMENT_AUTO_CREATE_AGENT",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        daily_improvement_state_path=os.getenv(
            "TERMIT_DAILY_IMPROVEMENT_STATE_PATH",
            "./data/ops/daily_improvement_state.json",
        ),
        skill_auto_select_enabled=os.getenv("TERMIT_SKILL_AUTO_SELECT_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        skill_auto_select_max=max(1, int(os.getenv("TERMIT_SKILL_AUTO_SELECT_MAX", "3"))),
        skill_auto_select_min_score=_parse_clamped_float_env(
            "TERMIT_SKILL_AUTO_SELECT_MIN_SCORE",
            3.0,
            min_value=0.0,
            max_value=100.0,
        ),
        media_enabled=os.getenv("TERMIT_MEDIA_ENABLED", "false").lower() in {"1", "true", "yes"},
        media_storage=os.getenv("TERMIT_MEDIA_STORAGE", "./data/media"),
        media_max_cost_usd=max(0.0, float(os.getenv("TERMIT_MEDIA_MAX_COST_USD", "25"))),
        media_confirm_cost_usd=max(0.0, float(os.getenv("TERMIT_MEDIA_CONFIRM_COST_USD", "1"))),
        media_image_provider=os.getenv("TERMIT_MEDIA_IMAGE_PROVIDER", "openai"),
        media_image_model=os.getenv("TERMIT_MEDIA_IMAGE_MODEL", "dall-e-3"),
        media_image_cost_usd=max(0.0, float(os.getenv("TERMIT_MEDIA_IMAGE_COST_USD", "0.08"))),
        media_tts_cost_usd=max(0.0, float(os.getenv("TERMIT_MEDIA_TTS_COST_USD", "0.015"))),
        media_transcribe_cost_usd=max(0.0, float(os.getenv("TERMIT_MEDIA_TRANSCRIBE_COST_USD", "0.006"))),
        media_tts_voice=os.getenv("TERMIT_MEDIA_TTS_VOICE", "alloy"),
        ffmpeg_path=os.getenv("TERMIT_FFMPEG_PATH", "ffmpeg"),
        ffprobe_path=os.getenv("TERMIT_FFPROBE_PATH", "ffprobe"),
        fal_api_key=os.getenv("FAL_KEY", ""),
        media_jobs_db_path=os.getenv("TERMIT_MEDIA_JOBS_DB_PATH", "./data/media/media_jobs.db"),
        media_i2v_provider=os.getenv("TERMIT_MEDIA_I2V_PROVIDER", "stub"),
        media_i2v_cost_usd=max(0.0, float(os.getenv("TERMIT_MEDIA_I2V_COST_USD", "0.50"))),
        media_brand_kits_dir=os.getenv("TERMIT_MEDIA_BRAND_KITS_DIR", "./data/media/brand_kits"),
        media_eval_scenarios_path=os.getenv(
            "TERMIT_MEDIA_EVAL_SCENARIOS_PATH",
            "./data/eval_scenarios_media.json",
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_api_base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
    )
