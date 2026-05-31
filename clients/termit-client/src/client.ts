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
}
