export interface PlatformSkillSummary {
  skill_id: string;
  name: string;
  description: string;
}

export interface PlatformSkillDetail extends PlatformSkillSummary {
  content: string;
}

export interface PlatformSkillListResponse {
  skills: PlatformSkillSummary[];
}

export interface PlatformSkillSelectRequest {
  instruction: string;
  task_type?: string;
  pinned_skill_ids?: string[];
  changed_files?: string[];
  max_skills?: number;
  auto_select_enabled?: boolean;
}

export interface PlatformSkillSelectionItem {
  skill_id: string;
  name: string;
  score: number;
  matched_terms: string[];
  source: string;
}

export interface PlatformSkillSelectResponse {
  selected_skill_ids: string[];
  selections: PlatformSkillSelectionItem[];
  auto_select_enabled: boolean;
}

export interface ProjectSkillsResponse {
  project_id: string;
  pinned_skill_ids: string[];
  available_skills: PlatformSkillSummary[];
}

export interface PlatformTraceSpan {
  span_id: string;
  run_id: string;
  name: string;
  detail: string;
  started_at: string;
  duration_ms: number;
}

export interface PlatformTraceSpanListResponse {
  run_id: string;
  spans: PlatformTraceSpan[];
}

export interface PlatformMcpServer {
  server_id: string;
  name: string;
  command: string;
  args: string[];
  enabled: boolean;
  allowed_tools: string[] | null;
}

export interface PlatformMcpServerListResponse {
  servers: PlatformMcpServer[];
}

export interface PlatformMcpInvokeResponse {
  result_json: string;
}

export interface PlatformMcpCapabilities {
  server_id: string;
  enabled: boolean;
  ping_ok: boolean;
  tools_count: number;
  resources_count: number;
  prompts_count: number;
  transport: string;
}

export interface PlatformMcpResourceSummary {
  uri: string;
  name: string;
  description: string;
  mime_type: string;
}

export interface PlatformMcpResourceListResponse {
  server_id: string;
  resources: PlatformMcpResourceSummary[];
}

export interface PlatformMcpPromptSummary {
  name: string;
  description: string;
  arguments: Array<Record<string, unknown>>;
}

export interface PlatformMcpPromptListResponse {
  server_id: string;
  prompts: PlatformMcpPromptSummary[];
}

export interface PlatformMcpResourceReadResponse {
  server_id: string;
  uri: string;
  contents: Array<Record<string, unknown>>;
}

export interface PlatformMcpPromptGetResponse {
  server_id: string;
  name: string;
  description: string;
  messages: Array<Record<string, unknown>>;
}

export interface PlatformAgentSchedule {
  schedule_id: string;
  agent_id: string;
  cron: string;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
}

export interface PlatformAgentScheduleListResponse {
  schedules: PlatformAgentSchedule[];
}

export interface PlatformHooksStatusResponse {
  enabled: boolean;
  webhook_configured: boolean;
  configured_events: string[];
}

export interface PlatformSearchStatusResponse {
  configured: boolean;
  provider: string;
}
