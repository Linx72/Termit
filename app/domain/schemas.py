from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    coding = "coding"
    review = "review"
    debug = "debug"
    explain = "explain"
    general = "general"


class TaskState(str, Enum):
    queued = "queued"
    running = "running"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskMode(str, Enum):
    auto = "auto"
    guided = "guided"


class ChatMessage(BaseModel):
    role: str = Field(default="user")
    content: str


class ChatRequest(BaseModel):
    message: str
    task_type: TaskType = TaskType.general
    model: Optional[str] = None
    session_id: Optional[str] = None
    use_memory: bool = True
    use_retrieval: bool = False
    use_repo_map: bool = True
    use_context_packing: bool = True
    retrieval_limit: int = Field(default=5, ge=1, le=20)
    retrieval_path_prefix: str = ""
    changed_files: list[str] = Field(default_factory=list)
    symbol_query: Optional[str] = None
    project_id: Optional[str] = None
    repo_profile: Optional[str] = None
    routing_policy: str = Field(default="default", pattern="^(default|benchmark)$")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1200, ge=64, le=8192)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    provider: str
    model: str
    task_type: TaskType
    session_id: Optional[str] = None
    history_size: int = 0
    attempted_models: list[str] = Field(default_factory=list)
    response: str
    context_compacted: bool = False
    dropped_messages: int = 0
    retrieval_hits: int = 0
    repo_profile: Optional[str] = None
    routing_policy: str = "default"
    selected_via: Optional[str] = None
    dual_pass_used: bool = False
    validator_model: Optional[str] = None


class FimCompletionRequest(BaseModel):
    prefix: str = Field(min_length=1, max_length=12000)
    suffix: str = Field(default="", max_length=4000)
    path: str = Field(default="", max_length=500)
    language: str = Field(default="", max_length=64)
    model: Optional[str] = None
    task_type: TaskType = TaskType.coding
    max_tokens: int = Field(default=64, ge=8, le=256)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)


class FimCompletionResponse(BaseModel):
    insert_text: str
    provider: str
    model: str
    attempted_models: list[str] = Field(default_factory=list)


class RepoModelProfileResponse(BaseModel):
    profile_id: str
    title: str
    path_prefix: str
    task_type: str
    preferred_model: str
    description: str = ""


class RoutingBenchmarkScoreResponse(BaseModel):
    model: str
    task_type: str
    score: float


class RoutingPolicyInfoResponse(BaseModel):
    repo_profiles: list[RepoModelProfileResponse] = Field(default_factory=list)
    benchmark_models: list[str] = Field(default_factory=list)


class RetrievalChunkResponse(BaseModel):
    path: str
    score: float
    line_start: int
    line_end: int
    excerpt: str


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)
    path_prefix: str = ""


class RetrievalSearchResponse(BaseModel):
    query: str
    total: int
    chunks: list[RetrievalChunkResponse] = Field(default_factory=list)


class RetrievalIndexResponse(BaseModel):
    indexed_files: int
    indexed_chunks: int
    retrieval_mode: str = "keyword"


class RepoMapResponse(BaseModel):
    summary: str
    root_path: str


class SymbolMatchResponse(BaseModel):
    name: str
    kind: str
    path: str
    line: int
    callers: list[str] = Field(default_factory=list)
    callees: list[str] = Field(default_factory=list)


class SymbolSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=30)
    path_prefix: str = ""


class SymbolSearchResponse(BaseModel):
    query: str
    total: int
    matches: list[SymbolMatchResponse] = Field(default_factory=list)


class ProjectRulesResponse(BaseModel):
    project_id: str
    project_rules: str = ""
    user_rules: str = ""
    skills: list[str] = Field(default_factory=list)


class ProjectRulesUpdateRequest(BaseModel):
    project_rules: str = ""
    user_rules: str = ""
    skills: list[str] = Field(default_factory=list)


class AgentTemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    task_type: TaskType
    system_prompt: str
    enabled_tools: list[str] = Field(default_factory=list)
    use_tool_loop: bool = False
    use_retrieval: bool = False


class AgentTemplateListResponse(BaseModel):
    templates: list[AgentTemplateResponse] = Field(default_factory=list)


class ProviderInfo(BaseModel):
    provider: str
    models: list[str]


class ProviderStatus(BaseModel):
    provider: str
    ok: bool
    detail: str


class LocalModelInfo(BaseModel):
    provider: str
    model: str
    size_bytes: Optional[int] = None
    modified_at: Optional[str] = None


class LocalModelsResponse(BaseModel):
    runtime: str
    models: list[LocalModelInfo] = Field(default_factory=list)


class LocalModelPullRequest(BaseModel):
    model: str = Field(min_length=2, max_length=200)


class LocalModelPullResponse(BaseModel):
    accepted: bool
    provider: str
    model: str
    status: str
    detail: str = ""


class LocalRuntimeStatusResponse(BaseModel):
    providers: list[ProviderStatus] = Field(default_factory=list)
    required_ollama_models: list[str] = Field(default_factory=list)
    missing_ollama_models: list[str] = Field(default_factory=list)
    retrieval_mode: str = "keyword"


class SessionHistoryResponse(BaseModel):
    session_id: str
    history: list[ChatMessage]


class SessionClearResponse(BaseModel):
    session_id: str
    cleared: bool


class SessionExportResponse(BaseModel):
    session_id: str
    format: str
    content: str
    message_count: int


class SessionExportFormat(str, Enum):
    markdown = "markdown"
    json = "json"
    txt = "txt"


class UsageStatusResponse(BaseModel):
    auth_enabled: bool
    api_key: Optional[str] = None
    role: Optional[str] = None
    team: Optional[str] = None
    used: int
    limit: int
    remaining: int
    usage_percent: float = 0.0
    team_used: Optional[int] = None
    team_limit: Optional[int] = None
    team_remaining: Optional[int] = None
    team_usage_percent: Optional[float] = None


class TeamUsageEntry(BaseModel):
    team: str
    used: int
    limit: Optional[int] = None
    remaining: Optional[int] = None
    usage_percent: Optional[float] = None
    member_keys: int = 0


class TeamListResponse(BaseModel):
    teams: list[str] = Field(default_factory=list)


class TeamUsageResponse(BaseModel):
    auth_enabled: bool
    entries: list[TeamUsageEntry] = Field(default_factory=list)


class OrchestrationRunRequest(BaseModel):
    input: str = Field(min_length=3, max_length=20000)
    task_type: TaskType = TaskType.coding
    model: Optional[str] = None
    session_id: Optional[str] = None
    use_retrieval: bool = True
    retrieval_limit: int = Field(default=5, ge=1, le=20)
    retrieval_path_prefix: str = ""
    repo_profile: Optional[str] = None
    routing_policy: str = Field(default="benchmark", pattern="^(default|benchmark)$")
    plan_only: bool = False


class OrchestrationPhaseResult(BaseModel):
    phase: str
    status: str
    detail: str
    duration_ms: int = 0


class OrchestrationRunResponse(BaseModel):
    run_id: str
    status: str
    plan_steps: list[str] = Field(default_factory=list)
    phases: list[OrchestrationPhaseResult] = Field(default_factory=list)
    report: str
    executor_response: str = ""
    session_id: Optional[str] = None


class OpsCheckResult(BaseModel):
    name: str
    passed: bool
    severity: str
    detail: str


class HealthzDependency(BaseModel):
    name: str
    status: str
    detail: str
    latency_ms: float = 0.0


class HealthzResponse(BaseModel):
    status: str
    version: str
    dependencies: list[HealthzDependency] = Field(default_factory=list)


class OpsReadinessResponse(BaseModel):
    status: str
    passed: int
    failed: int
    checks: list[OpsCheckResult] = Field(default_factory=list)


class OpsIncidentDrillResponse(BaseModel):
    run_id: str
    status: str
    passed: int
    failed: int
    checks: list[OpsCheckResult] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class QuotaEntrySummary(BaseModel):
    key_hint: str
    role: str
    team: str
    used: int
    limit: int
    remaining: int
    usage_percent: float


class QuotaSummaryResponse(BaseModel):
    auth_enabled: bool
    entries: list[QuotaEntrySummary] = Field(default_factory=list)


class QuotaResetRequest(BaseModel):
    api_key: str = Field(min_length=4, max_length=128)


class QuotaResetResponse(BaseModel):
    api_key: str
    reset: bool
    message: str


class AgentAlertThresholds(BaseModel):
    queue_utilization_percent: float = 80.0
    dead_letter_rate: float = 0.15
    min_worker_alive_ratio: float = 1.0


class MetricsActiveThresholds(BaseModel):
    degrade_empty_response_rate: float = 0.05
    degrade_fallback_rate: float = 0.35


class AlertThresholdsResponse(BaseModel):
    chat: MetricsActiveThresholds = Field(default_factory=MetricsActiveThresholds)
    agent: AgentAlertThresholds = Field(default_factory=AgentAlertThresholds)


class AgentRunsMetricsResponse(BaseModel):
    queue_size: int
    queue_capacity: int
    queue_utilization_percent: float
    worker_count: int
    alive_workers: int = 0
    total_runs: int
    by_state: dict[str, int] = Field(default_factory=dict)
    active_runs: int = 0
    dead_letter_rate: float = 0.0
    health_status: str = "ok"
    health_reasons: list[str] = Field(default_factory=list)
    active_thresholds: AgentAlertThresholds = Field(default_factory=AgentAlertThresholds)
    tool_loop_runs: int = 0
    tool_loop_tool_steps: int = 0
    tool_loop_tool_errors: int = 0
    tool_loop_parse_errors: int = 0
    tool_loop_final_steps: int = 0
    tool_loop_tool_success_rate: float = 0.0
    tool_loop_completion_rate: float = 0.0


class AgentRunsCleanupRequest(BaseModel):
    retention_days: int = Field(default=14, ge=1, le=365)
    dry_run: bool = False


class AgentRunsCleanupResponse(BaseModel):
    dry_run: bool
    retention_days: int
    cutoff_timestamp: str
    deleted_runs: int
    deleted_events: int
    remaining_runs: int


class MetricsSummaryResponse(BaseModel):
    chat_requests_total: int
    chat_success_total: int
    chat_cache_hits_total: int
    chat_cache_miss_total: int
    chat_success_rate: float
    chat_cache_hit_rate: float
    chat_latency_p50_ms: float
    chat_latency_p95_ms: float
    chat_empty_response_total: int = 0
    chat_code_response_total: int = 0
    chat_fallback_used_total: int = 0
    chat_avg_response_chars: float = 0.0
    chat_empty_response_rate: float = 0.0
    chat_code_response_rate: float = 0.0
    chat_fallback_rate: float = 0.0
    task_total: int
    task_completed: int
    task_failed: int
    task_success_rate: float
    automation_rate: float
    estimated_cost_total_usd: float
    model_usage: dict[str, int] = Field(default_factory=dict)
    failure_classes: dict[str, int] = Field(default_factory=dict)
    active_thresholds: MetricsActiveThresholds = Field(default_factory=MetricsActiveThresholds)
    health_status: str = "ok"
    health_reasons: list[str] = Field(default_factory=list)


class MetricsSnapshotResponse(BaseModel):
    captured_at: str
    metrics: MetricsSummaryResponse


class MetricsTrendPoint(BaseModel):
    captured_at: str
    chat_success_rate: float
    chat_cache_hit_rate: float
    chat_latency_p95_ms: float
    chat_empty_response_rate: float = 0.0
    chat_fallback_rate: float = 0.0
    task_success_rate: float
    automation_rate: float
    estimated_cost_total_usd: float


class MetricsTrendResponse(BaseModel):
    points: list[MetricsTrendPoint] = Field(default_factory=list)


class MetricsDailyReportDelta(BaseModel):
    chat_success_rate_delta: float
    chat_cache_hit_rate_delta: float
    chat_latency_p95_ms_delta: float
    task_success_rate_delta: float
    automation_rate_delta: float
    estimated_cost_total_usd_delta: float


class MetricsDailyReportResponse(BaseModel):
    period_days: int
    points_count: int
    latest: Optional[MetricsTrendPoint] = None
    previous: Optional[MetricsTrendPoint] = None
    delta: Optional[MetricsDailyReportDelta] = None


class MetricsExecutiveSummaryResponse(BaseModel):
    period_days: int
    points_count: int
    status: str
    improvements: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    latest: Optional[MetricsTrendPoint] = None
    previous: Optional[MetricsTrendPoint] = None


class MetricsSlackSummaryResponse(BaseModel):
    status: str
    text: str
    bullet_count: int


class MetricsSlackPayloadResponse(BaseModel):
    status: str
    should_notify: bool = False
    previous_status: Optional[str] = None
    payload: dict[str, object] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    message: str = Field(min_length=3, max_length=5000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    contact: Optional[str] = Field(default=None, max_length=200)
    session_id: Optional[str] = Field(default=None, max_length=120)
    task_id: Optional[str] = Field(default=None, max_length=120)
    run_id: Optional[str] = Field(default=None, max_length=120)
    instruction: Optional[str] = Field(default=None, max_length=8000)


class FeedbackResponse(BaseModel):
    status: str
    timestamp: str


class EvalScenarioResponse(BaseModel):
    id: str
    category: str
    title: str
    prompt: str


class EvalRunRequest(BaseModel):
    scenario_id: str = Field(min_length=2, max_length=20)


class EvalRunResponse(BaseModel):
    scenario_id: str
    category: str
    title: str
    status: str
    message: str
    prompt: str
    task_success: int = 0
    safety_compliance: int = 1
    automation_level: str = "manual assisted"
    duration_ms: int = 0
    failure_class: Optional[str] = None
    execution_ref: Optional[str] = None


class EvalSuiteRunRequest(BaseModel):
    category: Optional[str] = None
    limit: Optional[int] = Field(default=None, ge=1, le=100)
    persist_report: bool = True


class EvalSuiteRunResponse(BaseModel):
    run_id: str
    started_at: float
    finished_at: float
    total: int
    passed: int
    failed: int
    pass_rate: float
    category_filter: Optional[str] = None
    results: list[EvalRunResponse] = Field(default_factory=list)


class EvalReportSummaryResponse(BaseModel):
    reports: list[dict[str, object]] = Field(default_factory=list)
    total: int


class EvalDashboardResponse(BaseModel):
    pass_rate: float = 0.0
    latency_p95_ms: int = 0
    chat_latency_p95_ms: Optional[int] = None
    estimated_cost_usd: float = 0.0
    latest_run_id: Optional[str] = None
    latest_total: int = 0
    latest_passed: int = 0
    scenario_count: int = 0
    recent_reports: list[dict[str, object]] = Field(default_factory=list)


class ListFilesRequest(BaseModel):
    path: str = "."
    pattern: str = "*"


class ListFilesResponse(BaseModel):
    root: str
    path: str
    files: list[str]


class ReadFileRequest(BaseModel):
    path: str
    max_bytes: int = Field(default=20000, ge=256, le=200000)


class ReadFileResponse(BaseModel):
    path: str
    content: str
    truncated: bool = False


class ToolRiskLevel(str, Enum):
    safe = "safe"
    confirm = "confirm"
    blocked = "blocked"


class ExecuteCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)
    path: str = "."
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    dry_run: bool = False
    confirmed: bool = False


class ExecuteCommandResponse(BaseModel):
    command: str
    path: str
    risk_level: ToolRiskLevel
    policy_reason: str = ""
    executed: bool
    requires_confirmation: bool = False
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0


class ApplyPatchHunk(BaseModel):
    old_text: str = Field(default="", max_length=500000)
    new_text: str = Field(default="", max_length=500000)


class ApplyPatchRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    hunks: list[ApplyPatchHunk] = Field(default_factory=list)
    content: Optional[str] = Field(default=None, max_length=500000)
    create: bool = False
    dry_run: bool = False
    confirmed: bool = False


class ApplyPatchResponse(BaseModel):
    path: str
    risk_level: ToolRiskLevel
    policy_reason: str = ""
    applied: bool
    requires_confirmation: bool = False
    created: bool = False
    hunks_applied: int = 0
    bytes_written: int = 0
    preview_excerpt: str = ""


class ToolAuditEvent(BaseModel):
    timestamp: str
    tool_name: str
    action: str
    risk_level: ToolRiskLevel
    allowed: bool
    reason: str
    command: Optional[str] = None
    path: Optional[str] = None


class WebAutomationRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    objective: str = Field(default="Collect page evidence", min_length=3, max_length=500)
    max_steps: int = Field(default=4, ge=1, le=10)
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    capture_links_limit: int = Field(default=10, ge=1, le=50)


class WebEvidence(BaseModel):
    requested_url: str
    final_url: str
    status_code: int
    title: Optional[str] = None
    links: list[str] = Field(default_factory=list)
    snapshot_excerpt: str = ""


class WebAutomationResponse(BaseModel):
    objective: str
    success: bool
    blocker_detected: bool = False
    blocker_reason: Optional[str] = None
    steps: list[str] = Field(default_factory=list)
    evidence: Optional[WebEvidence] = None
    duration_ms: int = 0


class TaskCreateRequest(BaseModel):
    input: str = Field(min_length=3, max_length=20000)
    task_type: TaskType = TaskType.general
    mode: TaskMode = TaskMode.auto
    session_id: Optional[str] = None


class TaskEvent(BaseModel):
    event_type: str
    state: TaskState
    message: str
    timestamp: str


class TaskCreateResponse(BaseModel):
    task_id: str
    state: TaskState
    created_at: str


class TaskStatusResponse(BaseModel):
    task_id: str
    state: TaskState
    input: str
    task_type: TaskType
    mode: TaskMode
    session_id: Optional[str] = None
    created_at: str
    updated_at: str
    report: Optional[str] = None
    error: Optional[str] = None
    failure_class: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 0
    events: list[TaskEvent] = Field(default_factory=list)


class TaskCancelResponse(BaseModel):
    task_id: str
    cancelled: bool
    state: TaskState


class TaskListResponse(BaseModel):
    tasks: list[TaskStatusResponse] = Field(default_factory=list)
    total: int


class AgentProfileCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    system_prompt: str = Field(min_length=3, max_length=8000)
    task_type: TaskType = TaskType.general
    model: Optional[str] = None
    use_memory: bool = True
    use_retrieval: bool = False
    retrieval_limit: int = Field(default=5, ge=1, le=20)
    retrieval_path_prefix: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1200, ge=64, le=8192)
    allow_online: bool = False
    online_max_steps: int = Field(default=4, ge=1, le=10)
    online_timeout_seconds: int = Field(default=10, ge=1, le=60)
    online_capture_links_limit: int = Field(default=10, ge=1, le=50)
    enabled_tools: list[str] = Field(default_factory=list)
    use_tool_loop: bool = False
    max_tool_steps: int = Field(default=6, ge=1, le=20)
    use_long_term_memory: bool = True
    skill_ids: list[str] = Field(default_factory=list)


class AgentProfileResponse(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    system_prompt: str
    task_type: TaskType
    model: Optional[str] = None
    use_memory: bool = True
    use_retrieval: bool = False
    retrieval_limit: int = 5
    retrieval_path_prefix: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    allow_online: bool = False
    online_max_steps: int = 4
    online_timeout_seconds: int = 10
    online_capture_links_limit: int = 10
    enabled_tools: list[str] = Field(default_factory=list)
    use_tool_loop: bool = False
    max_tool_steps: int = 6
    use_long_term_memory: bool = True
    skill_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class AgentRunState(str, Enum):
    queued = "queued"
    running = "running"
    awaiting_confirmation = "awaiting_confirmation"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgentRunRequest(BaseModel):
    input: str = Field(min_length=1, max_length=20000)
    online_url: Optional[str] = None
    online_objective: Optional[str] = Field(default=None, max_length=500)
    session_id: Optional[str] = None
    use_memory: Optional[bool] = None
    use_retrieval: Optional[bool] = None
    retrieval_limit: Optional[int] = Field(default=None, ge=1, le=20)
    retrieval_path_prefix: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=64, le=8192)
    use_tool_loop: Optional[bool] = None
    priority: int = Field(default=0, ge=0, le=100)
    resume_checkpoint: Optional[dict[str, object]] = None
    workspace_scope: Optional[str] = None
    repo_profile: Optional[str] = None
    parent_run_id: Optional[str] = None
    project_id: Optional[str] = None
    changed_files: list[str] = Field(default_factory=list)


class AgentEvalRunRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=64)


class AgentEvalSuiteRunRequest(BaseModel):
    category: Optional[str] = Field(default=None, max_length=64)


class AgentMemoryListResponse(BaseModel):
    entries: list[dict[str, str]] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    agent_id: str
    agent_name: str
    provider: str
    model: str
    task_type: TaskType
    session_id: Optional[str] = None
    attempted_models: list[str] = Field(default_factory=list)
    response: str


class AgentRunRecordResponse(BaseModel):
    run_id: str
    agent_id: str
    agent_name: str
    state: AgentRunState
    created_at: str
    updated_at: str
    input: str
    session_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 1
    failure_class: Optional[str] = None
    attempted_models: list[str] = Field(default_factory=list)
    response: str = ""
    error: Optional[str] = None
    checkpoint_json: Optional[str] = None
    parent_run_id: Optional[str] = None


class AgentRunConfirmRequest(BaseModel):
    approved: bool = True


class AgentRunConfirmResponse(BaseModel):
    run_id: str
    state: AgentRunState
    resumed: bool = False


class AgentRunResumeResponse(BaseModel):
    run_id: str
    state: AgentRunState
    resumed: bool = False


class AgentRunEvent(BaseModel):
    event_type: str
    state: AgentRunState
    message: str
    timestamp: str
    attempt: int = 0


class AgentRunCreateResponse(BaseModel):
    run_id: str
    state: AgentRunState
    queued_position: int = 0


class AgentRunListResponse(BaseModel):
    runs: list[AgentRunRecordResponse] = Field(default_factory=list)
    total: int


class AgentRunCancelResponse(BaseModel):
    run_id: str
    cancelled: bool
    state: AgentRunState


class FinetuneDatasetExportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    include_feedback: bool = True
    include_tasks: bool = True
    include_agent_runs: bool = True
    include_chat_sessions: bool = True
    include_trajectory: bool = True
    include_training_signals: bool = True
    include_dpo_negatives: bool = True
    prefer_eval_passed: bool = True
    min_rating: int = Field(default=4, ge=1, le=5)
    min_samples: int = Field(default=1, ge=1, le=10000)
    limit: int = Field(default=500, ge=1, le=5000)
    curate_deduplicate: bool = True
    curate_dedup_output_prefix_len: int = Field(default=120, ge=0, le=2000)
    curate_min_output_chars: int = Field(default=12, ge=1, le=5000)
    curate_max_output_chars: int = Field(default=12000, ge=100, le=100000)
    curate_skip_error_patterns: bool = True
    curate_stratified_balance: bool = True
    curate_max_per_category: Optional[int] = Field(default=None, ge=1, le=5000)


class FinetuneDatasetExportResponse(BaseModel):
    name: str
    dataset_path: str
    sample_count: int
    format: str
    fields: list[str] = Field(default_factory=list)
    curation: dict[str, int] = Field(default_factory=dict)
    sources: dict[str, int] = Field(default_factory=dict)


class FinetuneTrajectoryExportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=200, ge=1, le=5000)
    min_samples: int = Field(default=1, ge=1, le=10000)
    success_only: bool = True
    min_messages: int = Field(default=3, ge=2, le=50)
    system_prompt: str = Field(default="", max_length=4000)


class FinetuneTrajectoryExportResponse(BaseModel):
    name: str
    dataset_path: str
    sample_count: int
    format: str = "sft_chat_jsonl"
    stats: dict[str, int] = Field(default_factory=dict)


class FinetuneDpoExportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=500, ge=1, le=5000)
    min_pairs: int = Field(default=1, ge=1, le=10000)
    min_chosen_chars: int = Field(default=12, ge=4, le=5000)


class FinetuneDpoExportResponse(BaseModel):
    name: str
    dataset_path: str
    pair_count: int
    format: str = "dpo_jsonl"
    negative_count: int = 0
    positive_pool: int = 0


class FinetuneTrainingDashboardResponse(BaseModel):
    stage1_runs: list[dict[str, object]] = Field(default_factory=list)
    latest_dataset: Optional[str] = None
    datasets_count: int = 0
    training_signals_count: int = 0
    eval_trend: list[dict[str, object]] = Field(default_factory=list)
    regression_gate_enabled: bool = True
    shadow_traffic_percent: float = 10.0
    tuning_report: dict[str, object] = Field(default_factory=dict)


class FinetuneTuningReportResponse(BaseModel):
    signal_origins: dict[str, int] = Field(default_factory=dict)
    event_stats: dict[str, object] = Field(default_factory=dict)
    dpo_negative_count: int = 0
    recommendations: list[str] = Field(default_factory=list)


class AgentRunReplayResponse(BaseModel):
    run_id: str
    replay_run_id: str
    agent_id: str
    state: AgentRunState


class AgentRunDlqReplayResponse(BaseModel):
    replayed: list[AgentRunCreateResponse] = Field(default_factory=list)
    count: int = 0


class FinetuneJobCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dataset_path: str = Field(min_length=1, max_length=500)
    sample_count: int = Field(ge=1, le=100000)
    base_model: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)


class FinetuneJobResponse(BaseModel):
    job_id: str
    name: str
    status: str
    dataset_path: str
    sample_count: int
    base_model: str
    created_at: str
    updated_at: str
    notes: str = ""
    adapter_model: Optional[str] = None


class FinetuneJobListResponse(BaseModel):
    jobs: list[FinetuneJobResponse] = Field(default_factory=list)


class FinetuneAdapterRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=200)
    base_model: str = Field(min_length=1, max_length=200)
    repo_profile_id: Optional[str] = None
    description: str = Field(default="", max_length=2000)


class FinetuneAdapterResponse(BaseModel):
    adapter_id: str
    name: str
    model: str
    base_model: str
    repo_profile_id: Optional[str] = None
    description: str = ""
    registered_at: str


class FinetuneAdapterListResponse(BaseModel):
    adapters: list[FinetuneAdapterResponse] = Field(default_factory=list)


class FinetuneRecipeResponse(BaseModel):
    base_model: str
    recommended_trainers: list[str] = Field(default_factory=list)
    modelfile_template: str
    dataset_format: dict[str, str] = Field(default_factory=dict)


class FinetuneStage1RunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_model: str = Field(default="ollama:deepseek-coder", min_length=1, max_length=200)
    include_feedback: bool = True
    include_tasks: bool = True
    include_agent_runs: bool = True
    min_rating: int = Field(default=4, ge=1, le=5)
    min_samples: int = Field(default=5, ge=1, le=10000)
    limit: int = Field(default=500, ge=1, le=5000)
    run_eval_baseline: bool = True
    run_post_eval: bool = True
    eval_category: Optional[str] = None
    eval_limit: Optional[int] = Field(default=24, ge=1, le=100)
    curate_deduplicate: bool = True
    curate_stratified_balance: bool = True
    export_trajectory_sft: bool = True
    notes: str = Field(default="", max_length=2000)
    auto_register_adapter: bool = False
    adapter_name: Optional[str] = Field(default=None, max_length=120)
    adapter_model: Optional[str] = Field(default=None, max_length=200)
    repo_profile_id: Optional[str] = None
    adapter_description: str = Field(default="", max_length=2000)


class FinetunePipelineStage(BaseModel):
    stage: str
    status: str
    detail: str


class FinetuneStage1RunResponse(BaseModel):
    pipeline_id: str
    status: str
    created_at: str
    dataset: FinetuneDatasetExportResponse
    baseline_run_id: Optional[str] = None
    baseline_pass_rate: Optional[float] = None
    baseline_total: Optional[int] = None
    baseline_passed: Optional[int] = None
    job: FinetuneJobResponse
    recipe: FinetuneRecipeResponse
    adapter: Optional[FinetuneAdapterResponse] = None
    stages: list[FinetunePipelineStage] = Field(default_factory=list)


class FinetunePipelineRunResponse(BaseModel):
    run_id: str
    status: str
    created_at: str
    updated_at: str
    cancelled: bool = False
    request: FinetuneStage1RunRequest
    result: Optional[FinetuneStage1RunResponse] = None
    error: Optional[str] = None
    stages: list[FinetunePipelineStage] = Field(default_factory=list)


class FinetunePipelineRunListResponse(BaseModel):
    runs: list[FinetunePipelineRunResponse] = Field(default_factory=list)
    total: int


class FinetunePipelineCancelResponse(BaseModel):
    run_id: str
    cancelled: bool
    status: str


class FinetuneTrainRequest(BaseModel):
    output_model: Optional[str] = Field(default=None, max_length=200)
    trainer_mode: Optional[str] = Field(default=None, max_length=32)
    auto_register_adapter: bool = False
    adapter_name: Optional[str] = Field(default=None, max_length=120)
    adapter_model: Optional[str] = Field(default=None, max_length=200)
    repo_profile_id: Optional[str] = None
    adapter_description: str = Field(default="", max_length=2000)


class FinetuneTrainResponse(BaseModel):
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    trainer_mode: str
    status: str
    output_model: Optional[str] = None
    modelfile_path: Optional[str] = None
    adapter_path: Optional[str] = None
    command: Optional[str] = None
    detail: str = ""
    duration_ms: int = 0
    adapter: Optional[FinetuneAdapterResponse] = None


class FinetuneStage1SchedulerStatusResponse(BaseModel):
    enabled: bool
    weekday: int
    hour_utc: int
    minute_utc: int
    name: str
    base_model: str
    min_samples: int
    run_eval_baseline: bool
    eval_limit: int
    auto_register_adapter: bool
    last_run_slot: Optional[str] = None
    last_run_id: Optional[str] = None
    last_run_at: Optional[str] = None
    last_run_source: Optional[str] = None
    thread_alive: bool = False


class SkillSummaryResponse(BaseModel):
    skill_id: str
    name: str
    description: str = ""


class SkillListResponse(BaseModel):
    skills: list[SkillSummaryResponse] = Field(default_factory=list)


class SkillDetailResponse(BaseModel):
    skill_id: str
    name: str
    description: str = ""
    content: str


class HookStatusResponse(BaseModel):
    enabled: bool
    webhook_configured: bool
    configured_events: list[str] = Field(default_factory=list)


class GuardrailCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    kind: str = Field(default="prompt", pattern="^(prompt|patch)$")


class GuardrailCheckResponse(BaseModel):
    allowed: bool
    reason: str = ""
    severity: str = "info"


class TraceSpanResponse(BaseModel):
    span_id: str
    run_id: str
    name: str
    status: str
    detail: str = ""
    duration_ms: int = 0
    created_at: str


class TraceSpanListResponse(BaseModel):
    run_id: str
    spans: list[TraceSpanResponse] = Field(default_factory=list)


class McpServerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    command: str = Field(min_length=1, max_length=500)
    args: list[str] = Field(default_factory=list)
    enabled: bool = True
    allowed_tools: list[str] = Field(default_factory=list)
    server_id: Optional[str] = None


class McpServerResponse(BaseModel):
    server_id: str
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    enabled: bool = True
    allowed_tools: list[str] = Field(default_factory=list)


class McpServerListResponse(BaseModel):
    servers: list[McpServerResponse] = Field(default_factory=list)


class McpInvokeRequest(BaseModel):
    tool_name: str = Field(min_length=1, max_length=120)
    arguments: dict[str, object] = Field(default_factory=dict)


class McpInvokeResponse(BaseModel):
    result_json: str


class AgentScheduleCreateRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=64)
    cron: str = Field(min_length=1, max_length=64)
    input: str = Field(min_length=1, max_length=20000)
    use_tool_loop: Optional[bool] = None


class AgentScheduleResponse(BaseModel):
    schedule_id: str
    agent_id: str
    cron: str
    enabled: bool = True
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None


class AgentScheduleListResponse(BaseModel):
    schedules: list[AgentScheduleResponse] = Field(default_factory=list)


class PlatformSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)


class PlatformSearchHitResponse(BaseModel):
    title: str
    url: str
    snippet: str


class PlatformSearchResponse(BaseModel):
    query: str
    provider: str
    hits: list[PlatformSearchHitResponse] = Field(default_factory=list)
