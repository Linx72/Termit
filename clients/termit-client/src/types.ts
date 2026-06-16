export type TaskType = "coding" | "review" | "debug" | "explain" | "general";

export interface ChatRequest {
  message: string;
  task_type?: TaskType;
  model?: string;
  session_id?: string;
  use_memory?: boolean;
  use_retrieval?: boolean;
  use_repo_map?: boolean;
  use_context_packing?: boolean;
  retrieval_limit?: number;
  retrieval_path_prefix?: string;
  changed_files?: string[];
  symbol_query?: string;
  project_id?: string;
  repo_profile?: string;
  routing_policy?: "default" | "benchmark";
  temperature?: number;
  max_tokens?: number;
  history?: Array<{ role: string; content: string }>;
}

export interface ChatResponse {
  provider: string;
  model: string;
  task_type: TaskType;
  session_id?: string;
  history_size: number;
  attempted_models: string[];
  response: string;
  context_compacted?: boolean;
  dropped_messages?: number;
  retrieval_hits?: number;
  repo_profile?: string;
  routing_policy?: string;
  selected_via?: string;
}

export interface ChatStreamMeta {
  provider: string;
  model: string;
  session_id: string;
  history_size: number;
  attempted_models: string[];
  context_compacted?: boolean;
  dropped_messages?: number;
  retrieval_hits?: number;
}

export interface ChatStreamEvent {
  event: "meta" | "token" | "done" | "error";
  data: Record<string, unknown>;
}

export interface TaskCreateRequest {
  input: string;
  task_type?: TaskType;
  mode?: "auto" | "guided";
  session_id?: string;
}

export interface TaskCreateResponse {
  task_id: string;
  state: string;
  created_at: string;
}

export interface TaskStatusResponse {
  task_id: string;
  state: string;
  input: string;
  task_type: TaskType;
  mode: string;
  session_id?: string;
  created_at: string;
  updated_at: string;
  report?: string;
  error?: string;
}

export interface TaskListResponse {
  tasks: TaskStatusResponse[];
  total: number;
}

export interface AgentProfile {
  agent_id: string;
  name: string;
  description?: string;
  system_prompt: string;
  task_type: TaskType;
  model?: string;
  enabled_tools?: string[];
  allowed_mcp_servers?: string[];
  max_tool_steps?: number;
  use_tool_loop?: boolean;
}

export interface AgentRunRequest {
  input: string;
  online_url?: string;
  online_objective?: string;
  session_id?: string;
  project_id?: string;
  changed_files?: string[];
  use_retrieval?: boolean;
  retrieval_path_prefix?: string;
  use_tool_loop?: boolean;
  workspace_scope?: string;
  policy_preset?: string;
  execution_mode?: "local" | "online" | "hybrid" | "ssh";
  auto_confirm_risky_tools?: boolean;
  verify_after_patch?: boolean;
  verify_max_retries?: number;
  ssh_host?: string;
  ssh_user?: string;
  ssh_port?: number;
  ssh_identity?: string;
  ssh_remote_path?: string;
  run_mode?: "agent" | "ask" | "plan";
}

export interface AgentRunCreateResponse {
  run_id: string;
  state: string;
  queued_position?: number;
}

export interface AgentRunRecord {
  run_id: string;
  agent_id: string;
  agent_name: string;
  state: string;
  created_at: string;
  updated_at: string;
  input: string;
  session_id?: string;
  provider?: string;
  model?: string;
  response?: string;
  error?: string;
  checkpoint_json?: string | null;
  parent_run_id?: string | null;
}

export interface AgentRunListResponse {
  runs: AgentRunRecord[];
  total: number;
}

export interface AgentRunEvent {
  event_type: string;
  state: string;
  message: string;
  timestamp: string;
  attempt?: number;
}

export interface AgentRunStreamEvent {
  event: "status" | "timeline" | "done" | "error" | "timeout";
  data: Record<string, unknown>;
}

export interface ProviderStatus {
  provider: string;
  ok: boolean;
  detail: string;
}

export interface ProviderInfo {
  provider: string;
  models: string[];
}

export interface ApplyPatchHunk {
  old_text: string;
  new_text: string;
}

export interface ApplyPatchRequest {
  path: string;
  hunks?: ApplyPatchHunk[];
  content?: string;
  create?: boolean;
  dry_run?: boolean;
  confirmed?: boolean;
}

export interface ApplyPatchResponse {
  path: string;
  risk_level: string;
  policy_reason?: string;
  applied: boolean;
  requires_confirmation?: boolean;
  created?: boolean;
  hunks_applied?: number;
  bytes_written?: number;
  preview_excerpt?: string;
}

export interface ListFilesRequest {
  path?: string;
  pattern?: string;
}

export interface ListFilesResponse {
  root: string;
  path: string;
  files: string[];
}

export interface ReadFileRequest {
  path: string;
  max_bytes?: number;
}

export interface ReadFileResponse {
  path: string;
  content: string;
  truncated?: boolean;
}

export interface ExecuteCommandRequest {
  command: string;
  path?: string;
  timeout_seconds?: number;
  dry_run?: boolean;
  confirmed?: boolean;
}

export interface ExecuteCommandResponse {
  command: string;
  path: string;
  risk_level: string;
  policy_reason?: string;
  executed: boolean;
  requires_confirmation?: boolean;
  exit_code?: number;
  stdout?: string;
  stderr?: string;
  duration_ms?: number;
}

export interface SymbolMatch {
  name: string;
  kind: string;
  path: string;
  line: number;
}

export interface SymbolSearchRequest {
  query: string;
  limit?: number;
  path_prefix?: string;
}

export interface SymbolSearchResponse {
  query: string;
  total: number;
  matches: SymbolMatch[];
}

export interface RetrievalStatsResponse {
  indexed_files: number;
  indexed_chunks: number;
  retrieval_mode?: string;
}

export interface AgentRunsMetrics {
  queue_size: number;
  queue_capacity: number;
  queue_utilization_percent: number;
  worker_count: number;
  alive_workers: number;
  health_status: string;
  active_runs: number;
  tool_loop_runs?: number;
  tool_loop_tool_steps?: number;
  tool_loop_tool_errors?: number;
  tool_loop_parse_errors?: number;
  tool_loop_tool_success_rate?: number;
  tool_loop_completion_rate?: number;
  lifecycle_terminal_runs_total?: number;
  lifecycle_completed_runs_total?: number;
  lifecycle_timeout_runs_total?: number;
  lifecycle_stale_total?: number;
  lifecycle_completion_rate?: number;
  stale_queued_runs?: number;
  stale_running_runs?: number;
  max_queued_age_seconds?: number;
  max_running_age_seconds?: number;
  queue_stuck_timeout_seconds?: number;
  dead_letter_rate?: number;
  health_reasons?: string[];
}

export interface EvalReportSummary {
  run_id?: string;
  timestamp?: number | string;
  pass_rate?: number;
  total?: number;
  passed?: number;
  failed?: number;
}

export interface FinetuneTrainingDashboard {
  stage1_runs: Array<Record<string, unknown>>;
  latest_dataset?: string | null;
  datasets_count: number;
  training_signals_count: number;
  eval_trend: Array<Record<string, unknown>>;
  regression_gate_enabled: boolean;
  shadow_traffic_percent: number;
  tuning_report: Record<string, unknown>;
}

export interface OpsReadiness {
  status: string;
  passed: number;
  failed: number;
}

export interface LocalModelInfo {
  name: string;
  size?: number;
  modified_at?: string;
}

export interface LocalModelsResponse {
  models: LocalModelInfo[];
}

export interface LocalModelPullResponse {
  model: string;
  status: string;
  message?: string;
}

export interface EvalDashboard {
  pass_rate: number;
  latency_p95_ms: number;
  chat_latency_p95_ms?: number;
  estimated_cost_usd: number;
  latest_run_id?: string;
  latest_total: number;
  latest_passed: number;
  scenario_count: number;
}

export interface PlatformSearchHit {
  title: string;
  url: string;
  snippet: string;
}

export interface PlatformSearchResponse {
  query: string;
  provider: string;
  hits: PlatformSearchHit[];
}

export interface RepoModelProfile {
  profile_id: string;
  title: string;
  path_prefix: string;
  task_type: string;
  preferred_model: string;
  description?: string;
  finetuned?: boolean;
}

export interface FinetuneAdapter {
  adapter_id: string;
  name: string;
  model: string;
  base_model: string;
  repo_profile_id?: string;
  description?: string;
  registered_at: string;
}
