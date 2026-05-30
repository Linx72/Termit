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
    retrieval_limit: int = Field(default=5, ge=1, le=20)
    retrieval_path_prefix: str = ""
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


class AgentRunsMetricsResponse(BaseModel):
    queue_size: int
    queue_capacity: int
    queue_utilization_percent: float
    worker_count: int
    total_runs: int
    by_state: dict[str, int] = Field(default_factory=dict)
    active_runs: int = 0


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


class MetricsActiveThresholds(BaseModel):
    degrade_empty_response_rate: float = 0.05
    degrade_fallback_rate: float = 0.35


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
    created_at: str
    updated_at: str


class AgentRunState(str, Enum):
    queued = "queued"
    running = "running"
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
    min_rating: int = Field(default=4, ge=1, le=5)
    min_samples: int = Field(default=1, ge=1, le=10000)
    limit: int = Field(default=500, ge=1, le=5000)


class FinetuneDatasetExportResponse(BaseModel):
    name: str
    dataset_path: str
    sample_count: int
    format: str
    fields: list[str] = Field(default_factory=list)


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
