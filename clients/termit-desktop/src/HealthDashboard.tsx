import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface HealthDashboardProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

interface HealthSnapshot {
  queueSize: number;
  queueCapacity: number;
  queueUtil: number;
  healthStatus: string;
  indexedFiles: number;
  indexedChunks: number;
  retrievalMode: string;
  readiness: string;
  evalPassRate: number | null;
  evalP95Ms: number | null;
  evalCostUsd: number | null;
  evalTotal: number | null;
  toolLoopSuccessRate: number | null;
  toolLoopCompletionRate: number | null;
  staleQueuedRuns: number;
  staleRunningRuns: number;
  maxQueuedAgeSeconds: number;
  maxRunningAgeSeconds: number;
  queueStuckTimeoutSeconds: number;
  trainingSignals: number | null;
  latestDataset: string | null;
  tuningHint: string | null;
}

interface LifecycleSummary {
  level: "ok" | "degraded" | "critical";
  staleTotal: number;
  maxAgeSeconds: number;
  timeoutSeconds: number;
}

function formatRate(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function buildLifecycleSummary(snapshot: HealthSnapshot): LifecycleSummary {
  const staleTotal = snapshot.staleQueuedRuns + snapshot.staleRunningRuns;
  const maxAgeSeconds = Math.max(snapshot.maxQueuedAgeSeconds, snapshot.maxRunningAgeSeconds);
  const timeoutSeconds = Math.max(1, snapshot.queueStuckTimeoutSeconds);
  const nearTimeout = maxAgeSeconds >= timeoutSeconds * 0.8;
  const level: LifecycleSummary["level"] =
    staleTotal > 0 ? "critical" : nearTimeout ? "degraded" : "ok";
  return { level, staleTotal, maxAgeSeconds, timeoutSeconds };
}

function lifecycleLabel(locale: Locale, level: LifecycleSummary["level"]): string {
  if (level === "critical") {
    return t(locale, "kpiLifecycleBad");
  }
  if (level === "degraded") {
    return t(locale, "kpiLifecycleWarn");
  }
  return t(locale, "kpiLifecycleOk");
}

export function HealthDashboard({ client, connected, locale }: HealthDashboardProps) {
  const [snapshot, setSnapshot] = useState<HealthSnapshot | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const [metrics, stats, readiness, training, evalDash] = await Promise.all([
        client.getAgentRunsMetrics(),
        client.getRetrievalStats(),
        client.getOpsReadiness(),
        client.getFinetuneTrainingDashboard(5),
        client.getEvalDashboard(1),
      ]);
      const passRate = evalDash.pass_rate ?? null;
      const recommendations = training.tuning_report?.recommendations;
      const tuningHint =
        Array.isArray(recommendations) && recommendations.length > 0
          ? String(recommendations[0])
          : null;
      setSnapshot({
        queueSize: metrics.queue_size,
        queueCapacity: metrics.queue_capacity,
        queueUtil: metrics.queue_utilization_percent,
        healthStatus: metrics.health_status,
        indexedFiles: stats.indexed_files,
        indexedChunks: stats.indexed_chunks,
        retrievalMode: stats.retrieval_mode ?? "—",
        readiness: readiness.status,
        evalPassRate: passRate,
        evalP95Ms: evalDash.latency_p95_ms ?? null,
        evalCostUsd: evalDash.estimated_cost_usd ?? null,
        evalTotal: evalDash.latest_total ?? null,
        toolLoopSuccessRate: metrics.tool_loop_tool_success_rate ?? null,
        toolLoopCompletionRate: metrics.tool_loop_completion_rate ?? null,
        staleQueuedRuns: metrics.stale_queued_runs ?? 0,
        staleRunningRuns: metrics.stale_running_runs ?? 0,
        maxQueuedAgeSeconds: metrics.max_queued_age_seconds ?? 0,
        maxRunningAgeSeconds: metrics.max_running_age_seconds ?? 0,
        queueStuckTimeoutSeconds: metrics.queue_stuck_timeout_seconds ?? 120,
        trainingSignals: training.training_signals_count,
        latestDataset: training.latest_dataset ?? null,
        tuningHint,
      });
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    }
  }, [client, connected]);

  useEffect(() => {
    void refresh();
    if (!connected) {
      return;
    }
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [connected, refresh]);

  return (
    <div className="health-dashboard" aria-label={t(locale, "healthTitle")}>
      <div className="health-dashboard-header">
        <strong>{t(locale, "healthTitle")}</strong>
        <button type="button" className="secondary compact" disabled={!connected} onClick={() => void refresh()}>
          ↻
        </button>
      </div>
      {error && <p className="hint error-text">{error}</p>}
      {snapshot ? (
        <ul className="health-stats">
          {(() => {
            const lifecycle = buildLifecycleSummary(snapshot);
            return (
              <>
                <li>
                  {t(locale, "queue")}: {snapshot.queueSize}/{snapshot.queueCapacity} ({snapshot.queueUtil.toFixed(0)}
                  %)
                </li>
                <li>
                  agents: <span className={`health-tag ${snapshot.healthStatus}`}>{snapshot.healthStatus}</span>
                </li>
                <li>
                  {t(locale, "index")}: {snapshot.indexedFiles} files · {snapshot.indexedChunks} chunks ·{" "}
                  {snapshot.retrievalMode}
                </li>
                <li>
                  {t(locale, "readiness")}: {snapshot.readiness}
                </li>
                <li>
                  {t(locale, "kpiEval")}: {formatRate(snapshot.evalPassRate)}
                  {snapshot.evalTotal != null ? ` · ${snapshot.evalTotal} ${t(locale, "kpiScenarios")}` : ""}
                  {snapshot.evalP95Ms != null ? ` · p95 ${snapshot.evalP95Ms}ms` : ""}
                  {snapshot.evalCostUsd != null ? ` · ~$${snapshot.evalCostUsd.toFixed(4)}` : ""}
                </li>
                <li>
                  {t(locale, "kpiToolLoop")}: {formatRate(snapshot.toolLoopSuccessRate)} · {t(locale, "kpiCompletion")}{" "}
                  {formatRate(snapshot.toolLoopCompletionRate)}
                </li>
                <li>
                  {t(locale, "kpiLifecycle")}:{" "}
                  <span className={`health-tag ${lifecycle.level}`}>{lifecycleLabel(locale, lifecycle.level)}</span> ·{" "}
                  {t(locale, "kpiCompletion")} {formatRate(snapshot.toolLoopCompletionRate)} ·{" "}
                  {t(locale, "kpiLifecycleStale")} q:{snapshot.staleQueuedRuns} r:{snapshot.staleRunningRuns} · max age{" "}
                  {lifecycle.maxAgeSeconds.toFixed(0)}s / {t(locale, "kpiLifecycleTimeout")} {lifecycle.timeoutSeconds}
                  s
                </li>
                <li>
                  {t(locale, "kpiTraining")}: {snapshot.trainingSignals ?? "—"} {t(locale, "kpiSignals")}
                  {snapshot.latestDataset ? ` · ${snapshot.latestDataset}` : ""}
                </li>
                {snapshot.tuningHint && (
                  <li className="hint muted">
                    {t(locale, "kpiTuning")}: {snapshot.tuningHint}
                  </li>
                )}
              </>
            );
          })()}
        </ul>
      ) : (
        <p className="hint muted">{connected ? "…" : "—"}</p>
      )}
    </div>
  );
}
