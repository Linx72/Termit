import type { TermitClient } from "./client";
import {
  buildInlineEditMessage,
  parseComposerPatches,
  pickInlinePatch,
} from "./composer";
import { computePatchedContent } from "./patchUtils";
import type {
  AgentRunEvent,
  AgentRunRecord,
  ApplyPatchRequest,
  ChatRequest,
  TaskType,
} from "./types";

const STOP_WATCH_STATES = new Set([
  "completed",
  "failed",
  "cancelled",
  "awaiting_confirmation",
]);

export interface InlineEditParams {
  instruction: string;
  filePath: string;
  languageId: string;
  selectedText: string;
  sessionId?: string;
  model?: string;
  taskType?: TaskType;
}

export interface InlineEditResult {
  patch: ApplyPatchRequest;
  sessionId?: string;
}

export function formatAgentTimeline(run: AgentRunRecord, events: AgentRunEvent[]): string {
  const lines = [
    `run: ${run.run_id}`,
    `state: ${run.state}`,
    run.model ? `model: ${run.model}` : "",
    run.error ? `error: ${run.error}` : "",
    "",
    "--- timeline ---",
  ].filter(Boolean);
  events.forEach((ev) => {
    lines.push(`[${ev.timestamp}] ${ev.state} · ${ev.event_type}: ${ev.message}`);
  });
  return lines.join("\n");
}

export async function fetchInlineEditPatch(
  client: TermitClient,
  params: InlineEditParams
): Promise<InlineEditResult> {
  const message = buildInlineEditMessage(
    params.instruction,
    params.filePath,
    params.languageId,
    params.selectedText
  );
  const response = await client.chat({
    message,
    task_type: params.taskType ?? "coding",
    session_id: params.sessionId,
    model: params.model,
    max_tokens: 2000,
    temperature: 0.2,
  });

  const patches = parseComposerPatches(response.response);
  const patch = pickInlinePatch(patches, params.filePath, params.selectedText);
  if (!patch?.hunks?.length) {
    throw new Error("Model did not return a valid patch JSON block.");
  }

  const hunk =
    patch.hunks.find((item) => item.old_text === params.selectedText) ?? patch.hunks[0];

  return {
    patch: {
      path: params.filePath,
      hunks: [{ old_text: hunk.old_text, new_text: hunk.new_text }],
    },
    sessionId: response.session_id,
  };
}

export function buildTabCompletionMessage(before: string, after: string): string {
  return [
    "Complete the code at the cursor. Return ONLY the text to insert at the cursor.",
    "No markdown, no explanation, no quotes.",
    "",
    "Before cursor:",
    "```",
    before.slice(-2500),
    "```",
    "",
    "After cursor:",
    "```",
    after.slice(0, 800),
    "```",
  ].join("\n");
}

export function parseTabCompletionResponse(text: string): string | undefined {
  const insertText = text.trim();
  if (!insertText || insertText.includes("\n\n")) {
    return undefined;
  }
  return insertText;
}

export async function requestTabCompletion(
  client: TermitClient,
  before: string,
  after: string,
  options: Pick<ChatRequest, "model" | "task_type"> = {}
): Promise<string | undefined> {
  try {
    const result = await client.fimComplete({
      prefix: before,
      suffix: after,
      model: options.model,
      task_type: options.task_type ?? "coding",
      max_tokens: 64,
      temperature: 0.1,
    });
    return parseTabCompletionResponse(result.insert_text);
  } catch {
    const response = await client.chat({
      message: buildTabCompletionMessage(before, after),
      task_type: options.task_type ?? "coding",
      model: options.model,
      max_tokens: 120,
      temperature: 0.1,
      use_memory: false,
    });
    return parseTabCompletionResponse(response.response);
  }
}

export interface AgentRunWatchOptions {
  pollMs?: number;
  timeoutSeconds?: number;
  signal?: AbortSignal;
}

export async function watchAgentRun(
  client: TermitClient,
  runId: string,
  onUpdate: (payload: { run: AgentRunRecord; events: AgentRunEvent[] }) => void,
  options: AgentRunWatchOptions = {}
): Promise<void> {
  let run: AgentRunRecord | null = null;
  let events: AgentRunEvent[] = [];

  const emit = () => {
    if (run) {
      onUpdate({ run, events });
    }
  };

  run = await client.getAgentRun(runId);
  events = await client.getAgentRunEvents(runId);
  emit();
  if (STOP_WATCH_STATES.has(run.state)) {
    return;
  }

  for await (const event of client.agentRunStream(runId, options)) {
    if (options.signal?.aborted) {
      break;
    }
    if (event.event === "status") {
      run = event.data as unknown as AgentRunRecord;
      emit();
      if (run && STOP_WATCH_STATES.has(run.state)) {
        break;
      }
    } else if (event.event === "timeline") {
      events = [...events, event.data as unknown as AgentRunEvent];
      emit();
    } else if (event.event === "done" || event.event === "timeout") {
      if (!run || !STOP_WATCH_STATES.has(run.state)) {
        run = await client.getAgentRun(runId);
        events = await client.getAgentRunEvents(runId);
        emit();
      }
      break;
    } else if (event.event === "error") {
      throw new Error(String(event.data.detail ?? "Agent stream error"));
    }
  }
}

export { computePatchedContent };
