import { TermitClient, type TermitClientOptions } from "./client";
import { TermitRunError, TermitStartupError } from "./errors";
import type {
  AgentProfile,
  AgentRunRecord,
  AgentRunRequest,
  AgentRunStreamEvent,
} from "./types";

export interface TermitAgentCreateOptions extends TermitClientOptions {
  profileId?: string;
  profileName?: string;
  /** Workspace root or path prefix scoped to agent runs (retrieval_path_prefix). */
  workspace?: string;
}

export interface TermitAgentSendOptions {
  payload?: Partial<AgentRunRequest>;
  pollMs?: number;
  timeoutSeconds?: number;
}

export class TermitRun {
  readonly runId: string;
  private readonly client: TermitClient;
  private readonly pollMs: number;
  private readonly timeoutSeconds: number;

  constructor(
    client: TermitClient,
    runId: string,
    options: { pollMs?: number; timeoutSeconds?: number } = {}
  ) {
    this.client = client;
    this.runId = runId;
    this.pollMs = options.pollMs ?? 500;
    this.timeoutSeconds = options.timeoutSeconds ?? 600;
  }

  stream(): AsyncGenerator<AgentRunStreamEvent> {
    return this.client.agentRunStream(this.runId, {
      pollMs: this.pollMs,
      timeoutSeconds: this.timeoutSeconds,
    });
  }

  async wait(timeoutSeconds = this.timeoutSeconds): Promise<AgentRunRecord> {
    const deadline = Date.now() + timeoutSeconds * 1000;
    let latest: AgentRunRecord | null = null;

    for await (const event of this.stream()) {
      if (Date.now() > deadline) {
        throw new TermitRunError("Run wait timeout", this.runId, "timeout");
      }
      if (event.event === "status") {
        latest = event.data as unknown as AgentRunRecord;
        if (latest.state === "completed") {
          return latest;
        }
        if (latest.state === "failed" || latest.state === "cancelled") {
          throw new TermitRunError(
            latest.error || `Run ${latest.state}`,
            this.runId,
            latest.state
          );
        }
      } else if (event.event === "done" || event.event === "timeout") {
        break;
      } else if (event.event === "error") {
        throw new TermitRunError(
          String(event.data.detail ?? "Agent stream error"),
          this.runId,
          "failed"
        );
      }
    }

    const record = latest ?? (await this.client.getAgentRun(this.runId));
    if (record.state === "completed") {
      return record;
    }
    if (record.state === "failed" || record.state === "cancelled") {
      throw new TermitRunError(record.error || `Run ${record.state}`, this.runId, record.state);
    }
    throw new TermitRunError("Run wait timeout", this.runId, "timeout");
  }
}

export class TermitAgent {
  readonly agentId: string;
  readonly workspace?: string;
  private readonly client: TermitClient;

  private constructor(client: TermitClient, agentId: string, workspace?: string) {
    this.client = client;
    this.agentId = agentId;
    this.workspace = workspace;
  }

  static async create(options: TermitAgentCreateOptions = {}): Promise<TermitAgent> {
    const client = new TermitClient(options);
    const workspace = options.workspace?.trim() || undefined;
    if (options.profileId) {
      return new TermitAgent(client, options.profileId, workspace);
    }
    const agents = await client.listAgents();
    if (options.profileName) {
      const match = agents.find((item) => item.name === options.profileName);
      if (!match) {
        throw new TermitStartupError(
          `Agent profile not found: ${options.profileName}`,
          404
        );
      }
      return new TermitAgent(client, match.agent_id, workspace);
    }
    if (agents.length === 0) {
      throw new TermitStartupError("No agent profiles configured", 404);
    }
    return new TermitAgent(client, agents[0].agent_id, workspace);
  }

  static async prompt(
    message: string,
    options: TermitAgentCreateOptions & TermitAgentSendOptions = {}
  ): Promise<AgentRunRecord> {
    const agent = await TermitAgent.create(options);
    const run = await agent.send(message, options);
    return run.wait(options.timeoutSeconds);
  }

  static async resume(
    runId: string,
    options: TermitClientOptions = {}
  ): Promise<TermitAgent> {
    const client = new TermitClient(options);
    let record = await client.getAgentRun(runId);
    if (["failed", "cancelled", "awaiting_confirmation"].includes(record.state)) {
      await client.resumeAgentRun(runId);
      record = await client.getAgentRun(runId);
    }
    return new TermitAgent(client, record.agent_id, options.workspace?.trim() || undefined);
  }

  async send(message: string, options: TermitAgentSendOptions = {}): Promise<TermitRun> {
    const payload: AgentRunRequest = {
      input: message,
      ...(this.workspace ? { retrieval_path_prefix: this.workspace } : {}),
      ...(options.payload ?? {}),
    };
    let created;
    try {
      created = await this.client.createAgentRun(this.agentId, payload);
    } catch (error) {
      const messageText = error instanceof Error ? error.message : String(error);
      throw new TermitStartupError(messageText, 502, true);
    }
    return new TermitRun(this.client, created.run_id, {
      pollMs: options.pollMs,
      timeoutSeconds: options.timeoutSeconds,
    });
  }

  listProfiles(): Promise<AgentProfile[]> {
    return this.client.listAgents();
  }
}
