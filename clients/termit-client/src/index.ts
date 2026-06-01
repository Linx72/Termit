export { TermitClient } from "./client";
export type { TermitClientOptions } from "./client";
export { TermitAgent, TermitRun } from "./agent";
export { TermitRunError, TermitStartupError } from "./errors";
export { parseSseStream } from "./sse";
export { parseAgentRunSseStream } from "./agentSse";
export * from "./composer";
export * from "./patchUtils";
export * from "./types";
export * from "./platform";
export {
  fetchInlineEditPatch,
  requestTabCompletion,
  formatAgentTimeline,
  watchAgentRun,
  buildTabCompletionMessage,
  parseTabCompletionResponse,
  computePatchedContent,
} from "./workflows";
export type {
  InlineEditParams,
  InlineEditResult,
  AgentRunWatchOptions,
} from "./workflows";
