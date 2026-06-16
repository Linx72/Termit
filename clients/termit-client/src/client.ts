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
  workspace?: string;
  fetchImpl?: typeof fetch;
}

export class TermitClient {
  readonly baseUrl: string;
  readonly apiKey?: string;
  readonly workspace?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: TermitClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:8765").replace(/\/$/, "");
    this.apiKey = options.apiKey;
    this.workspace = options.workspace?.trim() || undefined;
    const nativeFetch = typeof globalThis.fetch === "function" ? globalThis.fetch.bind(globalThis) : null;
    const providedFetch = options.fetchImpl
      ? ((input: RequestInfo | URL, init?: RequestInit) => options.fetchImpl!(input, init))
      : null;
    this.fetchImpl = providedFetch ?? nativeFetch ?? fetch;
  }

  private withWorkspace<T extends object>(payload: T): T {
    if (!this.workspace) {
      return payload;
    }
    const currentPrefix = (payload as { retrieval_path_prefix?: string }).retrieval_path_prefix;
    if (typeof currentPrefix === "string" && currentPrefix.trim().length > 0) {
      return payload;
    }
    return { ...payload, retrieval_path_prefix: this.workspace } as T;
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
      body: JSON.stringify(this.withWorkspace(payload)),
    });
  }

  async *chatStream(payload: ChatRequest): AsyncGenerator<ChatStreamEvent> {
    const response = await this.fetchImpl(`${this.baseUrl}/api/chat/stream`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(this.withWorkspace(payload)),
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
      body: JSON.stringify(this.withWorkspace(payload)),
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
    const body = this.withWorkspace({
      ...payload,
      workspace_scope: payload.workspace_scope ?? this.workspace,
      retrieval_path_prefix: payload.retrieval_path_prefix ?? this.workspace,
    });
    return this.request<AgentRunCreateResponse>(
      `/api/agents/${encodeURIComponent(agentId)}/runs`,
      {
        method: "POST",
        body: JSON.stringify(body),
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

  listChildRuns(runId: string, limit = 20): Promise<AgentRunListResponse> {
    return this.request<AgentRunListResponse>(
      `/api/agents/runs/${encodeURIComponent(runId)}/children?limit=${limit}`
    );
  }

  listDlqRuns(limit = 20): Promise<AgentRunListResponse> {
    return this.request<AgentRunListResponse>(
      `/api/agents/runs/dlq?limit=${encodeURIComponent(String(limit))}`
    );
  }

  replayDlqRuns(limit = 5): Promise<import("./types").AgentRunDlqReplayResponse> {
    return this.request<import("./types").AgentRunDlqReplayResponse>(
      `/api/agents/runs/dlq/replay?limit=${encodeURIComponent(String(limit))}`,
      { method: "POST" }
    );
  }

  replayAgentRun(runId: string): Promise<AgentRunCreateResponse> {
    return this.request<AgentRunCreateResponse>(
      `/api/agents/runs/${encodeURIComponent(runId)}/replay`,
      { method: "POST" }
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

  workspaceScripts(workspace?: string): Promise<{
    root: string;
    has_package_json: boolean;
    scripts: Record<string, string>;
    verify_command: string;
    dev_command: string;
  }> {
    const query =
      workspace && workspace.trim()
        ? `?workspace=${encodeURIComponent(workspace.trim())}`
        : "";
    return this.request(`/api/tools/workspace-scripts${query}`);
  }

  listAssignments(limit = 50): Promise<
    Array<{
      assignment_id: string;
      root_path: string;
      brief_path: string;
      deliverables_path: string;
      journal_path: string;
      created_at: string;
    }>
  > {
    return this.request(`/api/assignments?limit=${limit}`);
  }

  createAssignment(payload: {
    title: string;
    brief: string;
    success_criteria?: string[];
    target_urls?: string[];
  }): Promise<{
    assignment_id: string;
    root_path: string;
    brief_path: string;
    deliverables_path: string;
    journal_path: string;
    created_at: string;
  }> {
    return this.request("/api/assignments", {
      method: "POST",
      body: JSON.stringify(payload),
    });
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

  testSshConnection(payload: {
    host: string;
    user: string;
    remote_path: string;
    port?: number;
    identity_file?: string;
  }): Promise<{ ok: boolean; detail: string }> {
    return this.request("/api/tools/ssh/test", {
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

  importCursorProjectRules(
    projectId: string,
    payload: { workspace_root?: string; active_path?: string }
  ): Promise<{ project_id: string; project_rules: string; user_rules: string; skills: string[] }> {
    return this.request(`/api/projects/${encodeURIComponent(projectId)}/rules/import-cursor`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listMcpServerTools(serverId: string): Promise<{
    server_id: string;
    tools: Array<{ name: string; description?: string; input_schema?: Record<string, unknown> }>;
  }> {
    return this.request(`/api/platform/mcp/servers/${encodeURIComponent(serverId)}/tools`);
  }

  triggerAutomationWebhook(
    payload: {
      input: string;
      agent_id?: string;
      template_id?: string;
      project_id?: string;
      run_mode?: "agent" | "ask" | "plan";
      priority?: number;
    },
    webhookSecret: string
  ): Promise<{ run_id: string; state: string; agent_id: string; queued_position?: number }> {
    return this.request("/api/automation/webhook/agent-run", {
      method: "POST",
      headers: { "X-Termit-Webhook-Secret": webhookSecret },
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

  importPlatformCursorMcp(payload: {
    workspace_root?: string;
    path?: string;
  } = {}): Promise<{ imported: number; servers: import("./platform").PlatformMcpServer[] }> {
    return this.request("/api/platform/mcp/import-cursor", {
      method: "POST",
      body: JSON.stringify(payload),
    });
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

  getQuotaSummary(): Promise<import("./types").QuotaSummaryResponse> {
    return this.request("/api/ops/quota-summary");
  }

  getToolAudit(limit = 100): Promise<import("./types").ToolAuditEvent[]> {
    return this.request(`/api/tools/audit?limit=${encodeURIComponent(String(limit))}`);
  }

  getRuntimePolicy(): Promise<import("./types").AgentRuntimePolicy> {
    return this.request("/api/ops/runtime-policy");
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

  listCrossPlatformStacks(): Promise<import("./crossPlatform").CrossPlatformStacksResponse> {
    return this.request("/api/dev/cross-platform/stacks");
  }

  decomposeCrossPlatformTask(
    payload: import("./crossPlatform").CrossPlatformDecomposeRequest
  ): Promise<import("./crossPlatform").CrossPlatformDecomposeResult> {
    return this.request("/api/dev/cross-platform/decompose", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  prepareCrossPlatformStep(
    payload: import("./crossPlatform").CrossPlatformPrepareRequest
  ): Promise<import("./crossPlatform").CrossPlatformPrepareResult> {
    return this.request("/api/dev/cross-platform/prepare", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  detectCrossPlatformStack(
    workspacePath: string
  ): Promise<{ stack_id: string | null; hints: string[] }> {
    return this.request("/api/dev/cross-platform/detect-stack", {
      method: "POST",
      body: JSON.stringify({ workspace_path: workspacePath }),
    });
  }

  ensureAgentFromTemplate(templateId: string): Promise<AgentProfile> {
    return this.request<AgentProfile>(
      `/api/projects/agent-templates/${encodeURIComponent(templateId)}/ensure-agent`,
      { method: "POST", body: "{}" }
    );
  }

  recordCrossPlatformStep(payload: {
    goal: string;
    stack_id: string;
    step_id: string;
    step_index: number;
    verify_ok: boolean;
    verify_detail: string;
    plan_id?: string;
  }): Promise<{ recorded: boolean }> {
    return this.request("/api/dev/cross-platform/record-step", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  /** Internal helper for desktop parity APIs (`/api/desktop/*`). */
  requestDesktop<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, init);
  }

  /** Ops/automation APIs (`/api/ops/*`) for desktop settings. */
  requestOps<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, init);
  }

  /** Media Studio APIs (`/api/media/*`). */
  requestMedia<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, init);
  }

  /** Feedback APIs (`/api/feedback/*`). */
  requestFeedback<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, init);
  }
}
