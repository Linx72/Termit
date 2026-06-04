from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    coding = "coding"
    review = "review"
    debug = "debug"
    explain = "explain"
    general = "general"
    online_research = "online_research"
    online_project = "online_project"
    creative_media = "creative_media"


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
    allow_online: bool = False
    skill_ids: list[str] = Field(default_factory=list)


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
    runtime_primary_model: str = ""
    teacher_model: str = ""
    teacher_fallback_model: str = ""
    teacher_ollama_models: list[str] = Field(default_factory=list)


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


class CrossPlatformStackInfo(BaseModel):
    stack_id: str
    name: str
    description: str
    default_platforms: list[str] = Field(default_factory=list)
    build_verify: str = ""
    agent_template_id: str = ""


class CrossPlatformStacksResponse(BaseModel):
    stacks: list[CrossPlatformStackInfo] = Field(default_factory=list)


class CrossPlatformDecomposeRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=20000)
    stack_id: Optional[str] = None
    platforms: list[str] = Field(default_factory=list)
    include_game_loop: Optional[bool] = None
    persist_plan: bool = False
    workspace_path: str = ""


class CrossPlatformAtomicTaskInfo(BaseModel):
    step_id: str
    title: str
    detail: str
    platform: Optional[str] = None
    verify_hint: str = ""


class CrossPlatformDecomposeResponse(BaseModel):
    stack_id: str
    stack_name: str
    agent_template_id: str
    skill_id: str = "cross-platform-atomic"
    platforms: list[str] = Field(default_factory=list)
    build_verify: str = ""
    atomic_tasks: list[CrossPlatformAtomicTaskInfo] = Field(default_factory=list)
    first_step_prompt: str = ""
    plan_id: str = ""


class CrossPlatformDetectStackRequest(BaseModel):
    workspace_path: str = Field(min_length=1, max_length=2000)


class CrossPlatformDetectStackResponse(BaseModel):
    stack_id: Optional[str] = None
    hints: list[str] = Field(default_factory=list)


class CrossPlatformRecordStepRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=20000)
    stack_id: str = Field(min_length=1, max_length=64)
    step_id: str = Field(min_length=1, max_length=64)
    step_index: int = Field(ge=0, le=100)
    verify_ok: bool = False
    verify_detail: str = ""
    plan_id: Optional[str] = None


class CrossPlatformPrepareRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=20000)
    stack_id: Optional[str] = None
    platforms: list[str] = Field(default_factory=list)
    include_game_loop: Optional[bool] = None
    step_index: int = Field(default=0, ge=0, le=50)


class CrossPlatformPrepareResponse(BaseModel):
    stack_id: str
    stack_name: str
    agent_template_id: str
    skill_id: str = "cross-platform-atomic"
    platforms: list[str] = Field(default_factory=list)
    build_verify: str = ""
    step_index: int = 0
    step_count: int = 0
    step_id: str = ""
    step_title: str = ""
    verify_hint: str = ""
    prompt: str = ""
    atomic_tasks: list[CrossPlatformAtomicTaskInfo] = Field(default_factory=list)


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
    stale_queued_runs: int = 0
    stale_running_runs: int = 0
    max_queued_age_seconds: float = 0.0
    max_running_age_seconds: float = 0.0
    queue_stuck_timeout_seconds: int = 120


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
    cancelled_stale_runs: int = 0
    stale_before: str = ""


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


class WorkspaceScriptsResponse(BaseModel):
    root: str
    has_package_json: bool = False
    scripts: dict[str, str] = Field(default_factory=dict)
    verify_command: str = ""
    dev_command: str = ""


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


class AssignmentCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    brief: str = Field(min_length=10, max_length=20000)
    success_criteria: list[str] = Field(default_factory=list)
    target_urls: list[str] = Field(default_factory=list)


class AssignmentResponse(BaseModel):
    assignment_id: str
    root_path: str
    brief_path: str
    deliverables_path: str
    journal_path: str
    created_at: str


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
    policy_preset: Optional[str] = Field(default=None, max_length=32)
    execution_mode: Optional[str] = Field(default=None, max_length=16)
    skill_ids: list[str] = Field(default_factory=list)
    auto_select_skills: Optional[bool] = None
    auto_confirm_risky_tools: Optional[bool] = None
    verify_after_patch: Optional[bool] = None
    ssh_host: Optional[str] = Field(default=None, max_length=253)
    ssh_user: Optional[str] = Field(default=None, max_length=64)
    ssh_port: Optional[int] = Field(default=None, ge=1, le=65535)
    ssh_identity: Optional[str] = Field(default=None, max_length=2000)
    ssh_remote_path: Optional[str] = Field(default=None, max_length=2000)
    run_mode: Optional[str] = Field(default="agent", pattern="^(agent|ask|plan)$")


class SshConnectionTestRequest(BaseModel):
    host: str = Field(min_length=1, max_length=253)
    user: str = Field(min_length=1, max_length=64)
    remote_path: str = Field(min_length=1, max_length=2000)
    port: int = Field(default=22, ge=1, le=65535)
    identity_file: str = Field(default="", max_length=2000)


class SshConnectionTestResponse(BaseModel):
    ok: bool
    detail: str = ""


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
    base_model: str = Field(
        default="",
        max_length=200,
        description="Empty = TERMIT_TEACHER_MODEL / TERMIT_STAGE1_SCHEDULE_BASE_MODEL.",
    )
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


class DailyImprovementStatusResponse(BaseModel):
    enabled: bool
    hour_utc: int
    minute_utc: int
    agent_id: str = ""
    max_agent_runs: int = 3
    max_dlq_replay: int = 2
    max_eval_fixes: int = 2
    eval_probe_limit: int = 12
    run_eval_probe: bool = True
    auto_create_agent: bool = True
    last_run_slot: Optional[str] = None
    last_run_at: Optional[str] = None
    last_run_source: Optional[str] = None
    last_status: Optional[str] = None
    last_action_count: Optional[int] = None
    thread_alive: bool = False


class DailyImprovementPlanResponse(BaseModel):
    diagnostics: dict[str, object] = Field(default_factory=dict)
    actions: list[dict[str, object]] = Field(default_factory=list)
    action_count: int = 0


class DailyImprovementRunResponse(BaseModel):
    status: str
    source: Optional[str] = None
    detail: Optional[str] = None
    slot: Optional[str] = None
    agent_id: Optional[str] = None
    agent_source: Optional[str] = None
    plan: dict[str, object] = Field(default_factory=dict)
    results: list[dict[str, object]] = Field(default_factory=list)


class AutomationToggleItem(BaseModel):
    toggle_id: str
    env_key: Optional[str] = None
    label_ru: str
    label_en: str
    description_ru: str
    description_en: str
    enabled: bool
    requires_restart: bool = False


class AutomationPrefsResponse(BaseModel):
    env_path: str
    automatic_mode_enabled: bool
    toggles: list[AutomationToggleItem] = Field(default_factory=list)
    schedulers: dict[str, object] = Field(default_factory=dict)
    applied: list[str] = Field(default_factory=list)
    restart_recommended: bool = False


class AutomationPrefsUpdateRequest(BaseModel):
    toggles: dict[str, bool] = Field(default_factory=dict)
    automatic_mode_enabled: Optional[bool] = None


class SkillSummaryResponse(BaseModel):
    skill_id: str
    name: str
    description: str = ""


class SkillListResponse(BaseModel):
    skills: list[SkillSummaryResponse] = Field(default_factory=list)


class SkillSelectRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=20000)
    task_type: TaskType = TaskType.general
    pinned_skill_ids: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    max_skills: Optional[int] = Field(default=None, ge=1, le=10)
    auto_select_enabled: Optional[bool] = None


class SkillSelectionItemResponse(BaseModel):
    skill_id: str
    name: str
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    source: str


class SkillSelectResponse(BaseModel):
    selected_skill_ids: list[str] = Field(default_factory=list)
    selections: list[SkillSelectionItemResponse] = Field(default_factory=list)
    auto_select_enabled: bool = True


class SkillDetailResponse(BaseModel):
    skill_id: str
    name: str
    description: str = ""
    content: str


class HookStatusResponse(BaseModel):
    enabled: bool
    webhook_configured: bool
    configured_events: list[str] = Field(default_factory=list)
    local_script_hooks: int = 0


class McpCursorImportRequest(BaseModel):
    workspace_root: str = Field(default=".", max_length=4096)
    path: Optional[str] = Field(default=None, max_length=4096)


class McpCursorImportResponse(BaseModel):
    imported: int
    servers: list["McpServerResponse"] = Field(default_factory=list)


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


class McpToolResponse(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, object] = Field(default_factory=dict)


class McpToolListResponse(BaseModel):
    server_id: str
    tools: list[McpToolResponse] = Field(default_factory=list)


class ProjectRulesImportRequest(BaseModel):
    workspace_root: str = Field(default=".", max_length=4096)
    active_path: str = Field(default="", max_length=4096)


class AutomationAgentRunWebhookRequest(BaseModel):
    input: str = Field(min_length=1, max_length=20000)
    agent_id: Optional[str] = Field(default=None, max_length=64)
    template_id: Optional[str] = Field(default=None, max_length=64)
    project_id: Optional[str] = Field(default=None, max_length=256)
    run_mode: Optional[str] = Field(default="agent", pattern="^(agent|ask|plan)$")
    priority: int = Field(default=0, ge=0, le=100)


class AutomationAgentRunWebhookResponse(BaseModel):
    run_id: str
    state: str
    agent_id: str
    queued_position: int = 0


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


class DesktopJourneyResponse(BaseModel):
    journey_id: str
    title_ru: str
    title_en: str
    description_ru: str
    description_en: str
    modes: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    primary_tab: str = "chat"


class DesktopNorthStarResponse(BaseModel):
    journeys: list[DesktopJourneyResponse] = Field(default_factory=list)
    kpi_targets: dict[str, float] = Field(default_factory=dict)


class DesktopKpiGateItem(BaseModel):
    gate_id: str
    label: str
    actual: float
    target: float
    passed: bool
    higher_is_better: bool = True


class DesktopKpiGateResponse(BaseModel):
    overall_passed: bool
    passed_count: int
    total_gates: int
    gates: list[DesktopKpiGateItem] = Field(default_factory=list)
    targets: dict[str, float] = Field(default_factory=dict)
    journeys: list[DesktopJourneyResponse] = Field(default_factory=list)


class AgentPolicyPresetResponse(BaseModel):
    preset_id: str
    name: str
    description_ru: str = ""
    description_en: str = ""
    max_tool_steps: int = 6
    allow_online: bool = False
    auto_confirm_risky_tools: bool = False
    verify_after_patch: bool = True
    enabled_tools: list[str] = Field(default_factory=list)
    execution_mode: str = "local"


class DesktopShareRunRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=64)
    team: str = Field(default="default", max_length=64)
    note: str = Field(default="", max_length=500)
    shared_by: str = Field(default="desktop", max_length=64)


class DesktopShareRunResponse(BaseModel):
    share_id: str
    run_id: str
    team: str
    note: str = ""
    shared_by: str = "desktop"
    shared_at: str
    snapshot: dict[str, object] = Field(default_factory=dict)


class DesktopSharedRunListResponse(BaseModel):
    shared_runs: list[DesktopShareRunResponse] = Field(default_factory=list)
    total: int = 0


class DesktopHeavyJobRequest(BaseModel):
    job_type: str = Field(min_length=1, max_length=32)
    payload: dict[str, object] = Field(default_factory=dict)
    requested_by: str = Field(default="desktop", max_length=64)


class DesktopHeavyJobResponse(BaseModel):
    job_id: str
    job_type: str
    state: str
    payload: dict[str, object] = Field(default_factory=dict)
    requested_by: str = "desktop"
    created_at: str
    updated_at: str
    result: Optional[dict[str, object]] = None
    error: Optional[str] = None


class DesktopHeavyJobListResponse(BaseModel):
    jobs: list[DesktopHeavyJobResponse] = Field(default_factory=list)
    total: int = 0


class DesktopWorkflowEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    journey_id: str = Field(default="", max_length=64)
    execution_mode: str = Field(default="", max_length=16)
    duration_ms: Optional[int] = Field(default=None, ge=0, le=3_600_000)
    ok: Optional[bool] = None
    detail: str = Field(default="", max_length=500)
    metadata: dict[str, object] = Field(default_factory=dict)


class DesktopWorkflowEventResponse(BaseModel):
    event_id: str
    event_type: str
    timestamp: str


class MediaGenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    width: int = Field(default=1024, ge=64, le=4096)
    height: int = Field(default=1024, ge=64, le=4096)
    project_id: str = Field(default="default", max_length=120)
    run_id: Optional[str] = None
    scene_id: Optional[str] = None
    provider: Optional[str] = None
    confirmed: bool = False


class MediaAssetResponse(BaseModel):
    asset_id: str
    project_id: str
    rel_path: str
    mime: str
    width: int
    height: int
    provider: str
    cost_usd: float
    prompt: str
    created_at: str
    run_id: Optional[str] = None
    scene_id: Optional[str] = None


class MediaGenerateImageResponse(BaseModel):
    asset: MediaAssetResponse
    revised_prompt: Optional[str] = None


class MediaEstimateCostRequest(BaseModel):
    storyboard_path: Optional[str] = None


class MediaCostLineResponse(BaseModel):
    scene_id: str
    item: str
    usd: float


class MediaEstimateCostResponse(BaseModel):
    total_usd: float
    scene_count: int
    lines: list[MediaCostLineResponse] = Field(default_factory=list)


class MediaVisionQaRequest(BaseModel):
    asset_id: str
    criteria: str = ""
    min_score: float = Field(default=0.75, ge=0.0, le=1.0)


class MediaVisionQaResponse(BaseModel):
    score: float
    passed: bool
    notes: str


class MediaTtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    project_id: str = Field(default="default", max_length=120)
    run_id: Optional[str] = None
    voice_id: Optional[str] = None
    language: str = "ru"
    confirmed: bool = False


class MediaTtsResponse(BaseModel):
    asset: MediaAssetResponse


class MediaTranscribeRequest(BaseModel):
    asset_id: str
    project_id: str = Field(default="default", max_length=120)
    run_id: Optional[str] = None
    language: Optional[str] = None


class MediaTranscribeResponse(BaseModel):
    asset: MediaAssetResponse
    language: str


class MediaComposeRequest(BaseModel):
    project_id: str = Field(default="default", max_length=120)
    run_id: Optional[str] = None
    timeline_path: Optional[str] = None
    timeline: Optional[dict[str, object]] = None
    output_name: Optional[str] = None
    preset: str = "youtube_16x9"


class MediaComposeResponse(BaseModel):
    asset: MediaAssetResponse
    duration_sec: float


class MediaJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    provider: str
    payload: dict[str, object] = Field(default_factory=dict)
    result_asset_id: Optional[str] = None
    error: Optional[str] = None
    cost_usd: float = 0.0
    project_id: str = "default"
    run_id: Optional[str] = None


class MediaRenderVideoRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    source_asset_id: str
    project_id: str = "default"
    run_id: Optional[str] = None
    scene_id: Optional[str] = None
    duration_sec: float = Field(default=5.0, ge=1.0, le=30.0)
    provider: Optional[str] = None
    confirmed: bool = False


class MediaExportGifRequest(BaseModel):
    asset_ids: list[str] = Field(min_length=1)
    project_id: str = "default"
    run_id: Optional[str] = None
    fps: int = Field(default=8, ge=1, le=30)
    width: int = Field(default=480, ge=64, le=1920)


class MediaStoryboardRunRequest(BaseModel):
    storyboard_path: Optional[str] = None
    storyboard: Optional[dict[str, object]] = None
    project_id: str = "default"
    run_id: Optional[str] = None
    brand_kit_id: Optional[str] = None
    max_scenes: int = Field(default=6, ge=1, le=20)
    confirmed: bool = False


class BrandKitResponse(BaseModel):
    brand_kit_id: str
    name: str
    colors: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    logo_paths: list[str] = Field(default_factory=list)
    voice_id: str = ""
    music_mood: str = ""
    style_prompt_suffix: str = ""
