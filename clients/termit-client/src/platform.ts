export interface PlatformSkillSummary {
  skill_id: string;
  name: string;
  description: string;
}

export interface PlatformSkillDetail extends PlatformSkillSummary {
  body: string;
}

export interface PlatformSkillListResponse {
  skills: PlatformSkillSummary[];
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
