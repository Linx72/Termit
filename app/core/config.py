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
    agent_run_backend: str = "sqlite"
    agent_run_sqlite_path: str = "./termit_agent_runs.db"
    agent_registry_file_path: str = "./data/agents.json"
    agent_max_concurrency: int = 2
    agent_max_queue_size: int = 100
    agent_run_max_attempts: int = 2
    agent_run_retry_backoff_ms: int = 250
    agent_run_max_events_per_run: int = 500
    agent_run_max_response_chars: int = 12000
    agent_run_retention_days: int = 14
    response_cache_backend: str = "memory"
    response_cache_sqlite_path: str = "./termit_response_cache.db"
    response_cache_ttl_seconds: int = 120
    telemetry_max_latency_points: int = 5000
    metrics_snapshot_file_path: str = "./data/metrics_snapshots.jsonl"
    eval_report_file_path: str = "./data/eval_reports.jsonl"
    retrieval_enabled: bool = True
    retrieval_root_path: str = "."
    retrieval_max_chunks: int = 6
    retrieval_chunk_max_chars: int = 1200
    retrieval_max_file_bytes: int = 200000
    context_max_messages: int = 20
    context_max_chars: int = 12000
    context_summary_max_chars: int = 2000
    provider_retry_attempts: int = 2
    provider_retry_backoff_ms: int = 150
    degrade_empty_response_rate: float = 0.05
    degrade_fallback_rate: float = 0.35
    team_quotas: Dict[str, int] = field(default_factory=dict)
    repo_model_profiles_path: str = "./data/repo_model_profiles.json"
    routing_benchmarks_path: str = "./data/routing_benchmarks.json"
    finetune_datasets_dir: str = "./data/finetune/datasets"
    finetune_jobs_path: str = "./data/finetune/jobs.json"
    finetune_adapters_path: str = "./data/finetune/adapters.json"


def get_settings() -> Settings:
    return Settings(
        host=os.getenv("TERMIT_HOST", "0.0.0.0"),
        port=int(os.getenv("TERMIT_PORT", "8765")),
        allowed_origins=_split_csv(os.getenv("TERMIT_ALLOWED_ORIGINS", "*")),
        default_model=os.getenv("TERMIT_DEFAULT_MODEL", "ollama:deepseek-coder"),
        code_model=os.getenv("TERMIT_CODE_MODEL", "ollama:deepseek-coder"),
        analysis_model=os.getenv("TERMIT_ANALYSIS_MODEL", "ollama:qwen2.5-coder"),
        default_fallback_model=os.getenv(
            "TERMIT_DEFAULT_FALLBACK_MODEL",
            "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
        ),
        code_fallback_model=os.getenv(
            "TERMIT_CODE_FALLBACK_MODEL",
            "openai_compat:deepseek-ai/deepseek-coder-33b-instruct",
        ),
        analysis_fallback_model=os.getenv(
            "TERMIT_ANALYSIS_FALLBACK_MODEL",
            "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
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
        agent_run_max_events_per_run=int(os.getenv("TERMIT_AGENT_RUN_MAX_EVENTS_PER_RUN", "500")),
        agent_run_max_response_chars=int(os.getenv("TERMIT_AGENT_RUN_MAX_RESPONSE_CHARS", "12000")),
        agent_run_retention_days=int(os.getenv("TERMIT_AGENT_RUN_RETENTION_DAYS", "14")),
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
        retrieval_enabled=os.getenv("TERMIT_RETRIEVAL_ENABLED", "true").lower() in {"1", "true", "yes"},
        retrieval_root_path=os.getenv("TERMIT_RETRIEVAL_ROOT_PATH", "."),
        retrieval_max_chunks=int(os.getenv("TERMIT_RETRIEVAL_MAX_CHUNKS", "6")),
        retrieval_chunk_max_chars=int(os.getenv("TERMIT_RETRIEVAL_CHUNK_MAX_CHARS", "1200")),
        retrieval_max_file_bytes=int(os.getenv("TERMIT_RETRIEVAL_MAX_FILE_BYTES", "200000")),
        context_max_messages=int(os.getenv("TERMIT_CONTEXT_MAX_MESSAGES", "20")),
        context_max_chars=int(os.getenv("TERMIT_CONTEXT_MAX_CHARS", "12000")),
        context_summary_max_chars=int(os.getenv("TERMIT_CONTEXT_SUMMARY_MAX_CHARS", "2000")),
        provider_retry_attempts=int(os.getenv("TERMIT_PROVIDER_RETRY_ATTEMPTS", "2")),
        provider_retry_backoff_ms=int(os.getenv("TERMIT_PROVIDER_RETRY_BACKOFF_MS", "150")),
        degrade_empty_response_rate=_parse_clamped_float_env("TERMIT_DEGRADE_EMPTY_RATE", 0.05),
        degrade_fallback_rate=_parse_clamped_float_env("TERMIT_DEGRADE_FALLBACK_RATE", 0.35),
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
    )
