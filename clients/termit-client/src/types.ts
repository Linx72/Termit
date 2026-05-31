export type TaskType = "coding" | "review" | "debug" | "explain" | "general";

export interface ChatRequest {
  message: string;
  task_type?: TaskType;
  model?: string;
  session_id?: string;
  use_memory?: boolean;
  use_retrieval?: boolean;
  retrieval_limit?: number;
  retrieval_path_prefix?: string;
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
}

export interface AgentRunRequest {
  input: string;
  online_url?: string;
  online_objective?: string;
  session_id?: string;
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
  event: "status" | "done" | "error" | "timeout";
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
