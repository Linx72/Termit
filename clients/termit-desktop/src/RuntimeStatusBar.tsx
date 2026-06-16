import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface RuntimeStatusBarProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

interface RuntimeSnapshot {
  activeRuns: number;
  queueSize: number;
  queueCapacity: number;
  healthStatus: string;
  toolErrors: number;
  parseErrors: number;
  aliveWorkers: number;
  workerCount: number;
  topOutcomes: string;
}

function formatOutcomes(raw: Record<string, number> | undefined): string {
  if (!raw || Object.keys(raw).length === 0) {
    return "—";
  }
  return Object.entries(raw)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([key, count]) => `${key}:${count}`)
    .join(" · ");
}

export function RuntimeStatusBar({ client, connected, locale }: RuntimeStatusBarProps) {
  const [snapshot, setSnapshot] = useState<RuntimeSnapshot | null>(null);

  const refresh = useCallback(async () => {
    if (!connected) {
      setSnapshot(null);
      return;
    }
    try {
      const metrics = await client.getAgentRunsMetrics();
      const raw = metrics as Record<string, unknown>;
      const byOutcome =
        raw.by_outcome_class && typeof raw.by_outcome_class === "object"
          ? (raw.by_outcome_class as Record<string, number>)
          : undefined;
      setSnapshot({
        activeRuns: metrics.active_runs ?? 0,
        queueSize: metrics.queue_size,
        queueCapacity: metrics.queue_capacity,
        healthStatus: metrics.health_status,
        toolErrors: metrics.tool_loop_tool_errors ?? 0,
        parseErrors: metrics.tool_loop_parse_errors ?? 0,
        aliveWorkers: metrics.alive_workers ?? 0,
        workerCount: metrics.worker_count ?? 0,
        topOutcomes: formatOutcomes(byOutcome),
      });
    } catch {
      setSnapshot(null);
    }
  }, [client, connected]);

  useEffect(() => {
    void refresh();
    if (!connected) {
      return;
    }
    const timer = window.setInterval(() => void refresh(), 12_000);
    return () => window.clearInterval(timer);
  }, [connected, refresh]);

  if (!connected || !snapshot) {
    return null;
  }

  return (
    <div className="runtime-status-bar" aria-label={t(locale, "runtimeStatusTitle")}>
      <span>
        {t(locale, "runtimeActiveRuns")}: <strong>{snapshot.activeRuns}</strong>
      </span>
      <span>
        {t(locale, "queue")}: {snapshot.queueSize}/{snapshot.queueCapacity}
      </span>
      <span>
        {t(locale, "runtimeWorkers")}: {snapshot.aliveWorkers}/{snapshot.workerCount}
      </span>
      <span>
        {t(locale, "runtimeRetries")}: tool {snapshot.toolErrors} · parse {snapshot.parseErrors}
      </span>
      <span className={`health-tag ${snapshot.healthStatus}`}>{snapshot.healthStatus}</span>
      <span className="runtime-outcomes" title={t(locale, "runtimeOutcomes")}>
        {snapshot.topOutcomes}
      </span>
    </div>
  );
}
