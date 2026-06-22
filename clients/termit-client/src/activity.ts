import type { AgentRunEvent, AgentRunRecord } from "./types";

export type ActivityLocale = "ru" | "en";
export type ActivityFeedDetail = "compact" | "detailed" | "verbose";

export interface GitFallbackChange {
  path: string;
  status?: string;
}

export interface ReduceAgentActivityOptions {
  run?: Pick<AgentRunRecord, "state">;
  locale?: ActivityLocale;
  gitFallback?: GitFallbackChange[];
}

export interface FileEditActivity {
  path: string;
  operation: string;
  linesAdded: number;
  linesRemoved: number;
  pending: boolean;
  tool?: string;
  hunksApplied?: number;
}

export interface ToolActivity {
  tool: string;
  label: string;
  pending: boolean;
  timestamp: string;
}

export interface AgentActivitySummary {
  filesCount: number;
  linesAdded: number;
  linesRemoved: number;
  inProgress: boolean;
  label: string;
}

export interface AgentActivityState {
  fileEdits: FileEditActivity[];
  recentTools: ToolActivity[];
  summary: AgentActivitySummary;
}

function payloadOf(event: AgentRunEvent): Record<string, unknown> | undefined {
  const payload = event.payload;
  return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : undefined;
}

export function fileBasename(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

export function reduceAgentActivity(
  events: AgentRunEvent[],
  options: ReduceAgentActivityOptions = {}
): AgentActivityState {
  const locale = options.locale ?? "en";
  const run = options.run;
  const fileMap = new Map<string, FileEditActivity>();
  const recentTools: ToolActivity[] = [];

  for (const event of events) {
    const payload = payloadOf(event);
    if (!payload) {
      continue;
    }
    const kind = String(payload.kind ?? "");
    if (kind === "file_edit") {
      const path = String(payload.path ?? "").trim();
      if (!path) {
        continue;
      }
      fileMap.set(path, {
        path,
        operation: String(payload.operation ?? "edit"),
        linesAdded: Math.max(0, Number(payload.lines_added ?? 0)),
        linesRemoved: Math.max(0, Number(payload.lines_removed ?? 0)),
        pending: Boolean(payload.pending),
        tool: payload.tool ? String(payload.tool) : undefined,
        hunksApplied: payload.hunks_applied ? Number(payload.hunks_applied) : undefined,
      });
      continue;
    }
    if (kind === "tool") {
      recentTools.push({
        tool: String(payload.tool ?? ""),
        label: String(payload.label ?? event.message ?? payload.tool ?? "tool"),
        pending: Boolean(payload.pending),
        timestamp: event.timestamp,
      });
      continue;
    }
    if (kind === "activity_summary") {
      return {
        fileEdits: [...fileMap.values()],
        recentTools: recentTools.slice(-8),
        summary: {
          filesCount: Number(payload.files_count ?? fileMap.size),
          linesAdded: Number(payload.lines_added ?? 0),
          linesRemoved: Number(payload.lines_removed ?? 0),
          inProgress: Boolean(payload.in_progress),
          label: String(payload.label ?? ""),
        },
      };
    }
  }

  const fileEdits = [...fileMap.values()];
  const linesAdded = fileEdits.reduce((sum, item) => sum + item.linesAdded, 0);
  const linesRemoved = fileEdits.reduce((sum, item) => sum + item.linesRemoved, 0);
  const pending = fileEdits.some((item) => item.pending);
  const running =
    run?.state === "running" ||
    run?.state === "queued" ||
    run?.state === "verifying" ||
    pending;

  return {
    fileEdits,
    recentTools: recentTools.slice(-8),
    summary: {
      filesCount: fileEdits.length,
      linesAdded,
      linesRemoved,
      inProgress: running,
      label: formatActivitySummaryLabel(locale, {
        filesCount: fileEdits.length,
        linesAdded,
        linesRemoved,
        inProgress: running,
      }),
    },
  };
}

function mergeGitFallbackEdits(
  fileEdits: FileEditActivity[],
  gitFallback: GitFallbackChange[] | undefined
): FileEditActivity[] {
  if (fileEdits.length > 0 || !gitFallback?.length) {
    return fileEdits;
  }
  return gitFallback.map((item) => ({
    path: item.path,
    operation: item.status?.includes("?") || item.status?.toLowerCase().includes("a") ? "create" : "edit",
    linesAdded: 0,
    linesRemoved: 0,
    pending: false,
    tool: "git_fallback",
  }));
}

export function reduceAgentActivityWithFallback(
  events: AgentRunEvent[],
  options: ReduceAgentActivityOptions = {}
): AgentActivityState {
  const state = reduceAgentActivity(events, options);
  const fileEdits = mergeGitFallbackEdits(state.fileEdits, options.gitFallback);
  if (fileEdits === state.fileEdits) {
    return state;
  }
  const locale = options.locale ?? "en";
  const running = state.summary.inProgress;
  return {
    ...state,
    fileEdits,
    summary: {
      filesCount: fileEdits.length,
      linesAdded: state.summary.linesAdded,
      linesRemoved: state.summary.linesRemoved,
      inProgress: running,
      label: formatActivitySummaryLabel(locale, {
        filesCount: fileEdits.length,
        linesAdded: state.summary.linesAdded,
        linesRemoved: state.summary.linesRemoved,
        inProgress: running,
      }),
    },
  };
}

export function shouldShowLineStats(detail: ActivityFeedDetail): boolean {
  return detail === "detailed" || detail === "verbose";
}

export function shouldShowVerboseMeta(detail: ActivityFeedDetail): boolean {
  return detail === "verbose";
}

export function formatActivitySummaryLabel(
  locale: ActivityLocale,
  summary: Pick<AgentActivitySummary, "filesCount" | "linesAdded" | "linesRemoved" | "inProgress">
): string {
  if (summary.filesCount === 0 && !summary.inProgress) {
    return locale === "ru" ? "Пока без правок файлов" : "No file edits yet";
  }
  const stats =
    summary.filesCount > 0
      ? locale === "ru"
        ? `${summary.filesCount} файлов · +${summary.linesAdded} −${summary.linesRemoved}`
        : `${summary.filesCount} files · +${summary.linesAdded} −${summary.linesRemoved}`
      : "";
  if (summary.inProgress) {
    return locale === "ru"
      ? `${stats}${stats ? " · " : ""}Агент работает…`
      : `${stats}${stats ? " · " : ""}Agent is working…`;
  }
  return stats || (locale === "ru" ? "Готово" : "Done");
}

export function formatFileEditLabel(locale: ActivityLocale, edit: FileEditActivity): string {
  const name = fileBasename(edit.path);
  if (edit.pending) {
    return locale === "ru" ? `Правка ${name}…` : `Editing ${name}…`;
  }
  const op =
    edit.operation === "create"
      ? locale === "ru"
        ? "создан"
        : "created"
      : locale === "ru"
        ? "изменён"
        : "edited";
  return locale === "ru"
    ? `${name} · ${op} · +${edit.linesAdded} −${edit.linesRemoved}`
    : `${name} · ${op} · +${edit.linesAdded} −${edit.linesRemoved}`;
}

export function formatToolActivityLabel(tool: ToolActivity): string {
  return tool.label || tool.tool;
}
