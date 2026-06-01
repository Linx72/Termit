import { parseAgentRunSseStream } from "./agentSse";
import { parseSseStream } from "./sse";
import type {
  AgentProfile,
  AgentRunCreateResponse,
  AgentRunEvent,
  AgentRunListResponse,
  AgentRunRecord,
  AgentRunRequest,
  AgentRunStreamEvent,
  ApplyPatchRequest,
  ApplyPatchResponse,
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  ExecuteCommandRequest,
  ExecuteCommandResponse,
  ListFilesRequest,
  ListFilesResponse,
  ReadFileRequest,
  ReadFileResponse,
  ProviderStatus,
  ProviderInfo,
  RepoModelProfile,
  FinetuneAdapter,
  TaskCreateRequest,
  TaskCreateResponse,
  TaskListResponse,
  TaskStatusResponse,
} from "./types";

export interface TermitClientOptions {
  baseUrl?: string;
  apiKey?: string;
  fetchImpl?: typeof fetch;
}

export class TermitClient {
  readonly baseUrl: string;
  readonly apiKey?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: TermitClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:8765").replace(/\/$/, "");
    this.apiKey = options.apiKey;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  private headers(extra?: HeadersInit): HeadersInit {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return { ...headers, ...(extra as Record<string, string> | undefined) };
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers: this.headers(init?.headers),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Termit API ${response.status}: ${detail}`);
    }

    return (await response.json()) as T;
  }

  chat(payload: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async *chatStream(payload: ChatRequest): AsyncGenerator<ChatStreamEvent> {
    const response = await this.fetchImpl(`${this.baseUrl}/api/chat/stream`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Termit API ${response.status}: ${detail}`);
    }

    yield* parseSseStream(response.body);
  }

  createTask(payload: TaskCreateRequest): Promise<TaskCreateResponse> {
    return this.request<TaskCreateResponse>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  getTask(taskId: string): Promise<TaskStatusResponse> {
    return this.request<TaskStatusResponse>(`/api/tasks/${encodeURIComponent(taskId)}`);
  }

  listTasks(limit = 50): Promise<TaskListResponse> {
    return this.request<TaskListResponse>(`/api/tasks?limit=${limit}`);
  }

  listAgents(): Promise<AgentProfile[]> {
    return this.request<AgentProfile[]>("/api/agents");
  }

  createAgentRun(agentId: string, payload: AgentRunRequest): Promise<AgentRunCreateResponse> {
    return this.request<AgentRunCreateResponse>(
      `/api/agents/${encodeURIComponent(agentId)}/runs`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  }

  getAgentRun(runId: string): Promise<AgentRunRecord> {
    return this.request<AgentRunRecord>(`/api/agents/runs/${encodeURIComponent(runId)}`);
  }

  listAgentRuns(agentId: string, limit = 20): Promise<AgentRunListResponse> {
    return this.request<AgentRunListResponse>(
      `/api/agents/${encodeURIComponent(agentId)}/runs?limit=${limit}`
    );
  }

  getAgentRunEvents(runId: string): Promise<AgentRunEvent[]> {
    return this.request<AgentRunEvent[]>(
      `/api/agents/runs/${encodeURIComponent(runId)}/events`
    );
  }

  confirmAgentRun(runId: string, approved: boolean): Promise<{ run_id: string; state: string; resumed: boolean }> {
    return this.request(`/api/agents/runs/${encodeURIComponent(runId)}/confirm`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    });
  }

  resumeAgentRun(runId: string): Promise<{ run_id: string; state: string; resumed: boolean }> {
    return this.request(`/api/agents/runs/${encodeURIComponent(runId)}/resume`, {
      method: "POST",
      body: "{}",
    });
  }

  fimComplete(payload: {
    prefix: string;
    suffix?: string;
    path?: string;
    language?: string;
    model?: string;
    task_type?: import("./types").TaskType;
    max_tokens?: number;
    temperature?: number;
  }): Promise<{ insert_text: string; provider: string; model: string; attempted_models: string[] }> {
    return this.request("/api/completion/fim", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async *agentRunStream(
    runId: string,
    options: { pollMs?: number; timeoutSeconds?: number } = {}
  ): AsyncGenerator<AgentRunStreamEvent> {
    const pollMs = options.pollMs ?? 500;
    const timeoutSeconds = options.timeoutSeconds ?? 600;
    const query = new URLSearchParams({
      poll_ms: String(pollMs),
      timeout_seconds: String(timeoutSeconds),
    });
    const response = await this.fetchImpl(
      `${this.baseUrl}/api/agents/runs/${encodeURIComponent(runId)}/stream?${query}`,
      { headers: this.headers() }
    );

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Termit API ${response.status}: ${detail}`);
    }

    yield* parseAgentRunSseStream(response.body);
  }

  health(): Promise<{ status: string }> {
    return this.request<{ status: string }>("/health");
  }

  healthz(): Promise<{ status: string; version: string }> {
    return this.request<{ status: string; version: string }>("/healthz");
  }

  reindexRetrieval(): Promise<{
    indexed_files: number;
    indexed_chunks: number;
    retrieval_mode?: string;
  }> {
    return this.request<{
      indexed_files: number;
      indexed_chunks: number;
      retrieval_mode?: string;
    }>("/api/retrieval/reindex", { method: "POST", body: "{}" });
  }

  localRuntimeStatus(): Promise<{
    providers: ProviderStatus[];
    required_ollama_models?: string[];
    missing_ollama_models?: string[];
    retrieval_mode?: string;
  }> {
    return this.request("/api/local/status");
  }

  providersStatus(): Promise<ProviderStatus[]> {
    return this.request<ProviderStatus[]>("/api/providers/status");
  }

  listProviders(): Promise<ProviderInfo[]> {
    return this.request<ProviderInfo[]>("/api/providers");
  }

  listRepoProfiles(): Promise<RepoModelProfile[]> {
    return this.request<RepoModelProfile[]>("/api/routing/profiles");
  }

  listFinetuneAdapters(): Promise<{ adapters: FinetuneAdapter[] }> {
    return this.request<{ adapters: FinetuneAdapter[] }>("/api/finetune/adapters");
  }

  applyPatch(payload: ApplyPatchRequest): Promise<ApplyPatchResponse> {
    return this.request<ApplyPatchResponse>("/api/tools/apply_patch", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  readFile(payload: ReadFileRequest): Promise<ReadFileResponse> {
    return this.request<ReadFileResponse>("/api/tools/read_file", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listFiles(payload: ListFilesRequest = {}): Promise<ListFilesResponse> {
    return this.request<ListFilesResponse>("/api/tools/list_files", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  executeCommand(payload: ExecuteCommandRequest): Promise<ExecuteCommandResponse> {
    return this.request<ExecuteCommandResponse>("/api/tools/execute_command", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  getProjectRules(projectId: string): Promise<{
    project_id: string;
    project_rules: string;
    user_rules: string;
    skills: string[];
  }> {
    return this.request(`/api/projects/${encodeURIComponent(projectId)}/rules`);
  }

  saveProjectRules(
    projectId: string,
    payload: { project_rules: string; user_rules: string; skills: string[] }
  ): Promise<{ project_id: string; project_rules: string; user_rules: string; skills: string[] }> {
    return this.request(`/api/projects/${encodeURIComponent(projectId)}/rules`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listAgentTemplates(): Promise<{ templates: Array<{ template_id: string; name: string; description: string }> }> {
    return this.request("/api/projects/agent-templates");
  }

  getRepoMap(pathPrefix = ""): Promise<{ summary: string; root_path: string }> {
    const query = pathPrefix ? `?path_prefix=${encodeURIComponent(pathPrefix)}` : "";
    return this.request(`/api/retrieval/repo-map${query}`);
  }

  listPlatformSkills(): Promise<import("./platform").PlatformSkillListResponse> {
    return this.request("/api/platform/skills");
  }

  getPlatformSkill(skillId: string): Promise<import("./platform").PlatformSkillDetail> {
    return this.request(`/api/platform/skills/${encodeURIComponent(skillId)}`);
  }

  listPlatformMcpServers(): Promise<import("./platform").PlatformMcpServerListResponse> {
    return this.request("/api/platform/mcp/servers");
  }

  upsertPlatformMcpServer(payload: {
    server_id?: string;
    name: string;
    command: string;
    args?: string[];
    enabled?: boolean;
    allowed_tools?: string[];
  }): Promise<import("./platform").PlatformMcpServer> {
    return this.request("/api/platform/mcp/servers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  invokePlatformMcpTool(
    serverId: string,
    toolName: string,
    args: Record<string, unknown> = {}
  ): Promise<import("./platform").PlatformMcpInvokeResponse> {
    return this.request(`/api/platform/mcp/servers/${encodeURIComponent(serverId)}/invoke`, {
      method: "POST",
      body: JSON.stringify({ tool_name: toolName, arguments: args }),
    });
  }

  listPlatformSchedules(agentId?: string): Promise<import("./platform").PlatformAgentScheduleListResponse> {
    const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
    return this.request(`/api/platform/schedules${query}`);
  }

  createPlatformSchedule(payload: {
    agent_id: string;
    cron: string;
    input: string;
    use_tool_loop?: boolean;
  }): Promise<import("./platform").PlatformAgentSchedule> {
    return this.request("/api/platform/schedules", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listRunSpans(runId: string, limit = 100): Promise<import("./platform").PlatformTraceSpanListResponse> {
    return this.request(
      `/api/platform/runs/${encodeURIComponent(runId)}/spans?limit=${encodeURIComponent(String(limit))}`
    );
  }

  getPlatformHooksStatus(): Promise<import("./platform").PlatformHooksStatusResponse> {
    return this.request("/api/platform/hooks/status");
  }

  getPlatformSearchStatus(): Promise<import("./platform").PlatformSearchStatusResponse> {
    return this.request("/api/platform/search/status");
  }

  searchSymbols(payload: import("./types").SymbolSearchRequest): Promise<import("./types").SymbolSearchResponse> {
    return this.request("/api/retrieval/symbols/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  getRetrievalStats(): Promise<import("./types").RetrievalStatsResponse> {
    return this.request("/api/retrieval/stats");
  }

  getOpsReadiness(): Promise<import("./types").OpsReadiness> {
    return this.request("/api/ops/readiness");
  }

  getAgentRunsMetrics(): Promise<import("./types").AgentRunsMetrics> {
    return this.request("/api/ops/agent-runs/metrics");
  }

  getFinetuneTrainingDashboard(limit = 10): Promise<import("./types").FinetuneTrainingDashboard> {
    return this.request(`/api/finetune/training/dashboard?limit=${encodeURIComponent(String(limit))}`);
  }

  listEvalReports(limit = 10): Promise<{ reports: import("./types").EvalReportSummary[]; total: number }> {
    return this.request(`/api/eval/reports?limit=${encodeURIComponent(String(limit))}`);
  }

  listLocalModels(): Promise<import("./types").LocalModelsResponse> {
    return this.request("/api/local/models");
  }

  pullOllamaModel(model: string): Promise<import("./types").LocalModelPullResponse> {
    return this.request("/api/local/models/pull", {
      method: "POST",
      body: JSON.stringify({ model }),
    });
  }

  getEvalDashboard(limit = 10): Promise<import("./types").EvalDashboard> {
    return this.request(`/api/eval/dashboard?limit=${limit}`);
  }

  searchWeb(query: string, maxResults = 5): Promise<import("./types").PlatformSearchResponse> {
    return this.request("/api/platform/search", {
      method: "POST",
      body: JSON.stringify({ query, max_results: maxResults }),
    });
  }
}
