import { useCallback, useEffect, useState } from "react";
import type { AgentRunRecord, TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface AgentObservabilityPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

interface OpsSnapshot {
  deadLetterRate: number | null;
  healthReasons: string[];
  toolErrors: number | null;
  parseErrors: number | null;
  evalP95Ms: number | null;
  dlqRuns: AgentRunRecord[];
}

export function AgentObservabilityPanel({ client, connected, locale }: AgentObservabilityPanelProps) {
  const [snapshot, setSnapshot] = useState<OpsSnapshot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const [metrics, evalDash, dlq] = await Promise.all([
        client.getAgentRunsMetrics(),
        client.getEvalDashboard(1),
        client.listDlqRuns(10),
      ]);
      const raw = metrics as Record<string, unknown>;
      setSnapshot({
        deadLetterRate:
          typeof raw.dead_letter_rate === "number" ? raw.dead_letter_rate : null,
        healthReasons: Array.isArray(raw.health_reasons)
          ? raw.health_reasons.map(String)
          : [],
        toolErrors:
          typeof metrics.tool_loop_tool_errors === "number"
            ? metrics.tool_loop_tool_errors
            : null,
        parseErrors:
          typeof metrics.tool_loop_parse_errors === "number"
            ? metrics.tool_loop_parse_errors
            : null,
        evalP95Ms: evalDash.latency_p95_ms ?? null,
        dlqRuns: dlq.runs ?? [],
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
    const timer = window.setInterval(() => void refresh(), 20_000);
    return () => window.clearInterval(timer);
  }, [connected, refresh]);

  const replayAll = async () => {
    if (!connected || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await client.replayDlqRuns(5);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const replayOne = async (runId: string) => {
    if (!connected || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await client.replayAgentRun(runId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="agent-observability" aria-label={t(locale, "observabilityTitle")}>
      <div className="health-dashboard-header">
        <strong>{t(locale, "observabilityTitle")}</strong>
        <button type="button" className="secondary compact" disabled={!connected} onClick={() => void refresh()}>
          ↻
        </button>
      </div>
      {error ? <p className="hint error-text">{error}</p> : null}
      {snapshot ? (
        <>
          <ul className="health-stats">
            <li>
              {t(locale, "obsDeadLetter")}:{" "}
              {snapshot.deadLetterRate != null
                ? `${(snapshot.deadLetterRate * 100).toFixed(1)}%`
                : "—"}
            </li>
            <li>
              {t(locale, "obsToolErrors")}: {snapshot.toolErrors ?? "—"} · {t(locale, "obsParseErrors")}:{" "}
              {snapshot.parseErrors ?? "—"}
            </li>
            <li>
              {t(locale, "obsLatency")}: {snapshot.evalP95Ms != null ? `${snapshot.evalP95Ms}ms p95` : "—"}
            </li>
            {snapshot.healthReasons.length > 0 ? (
              <li className="hint muted">{snapshot.healthReasons.join("; ")}</li>
            ) : null}
          </ul>
          <div className="dlq-panel">
            <div className="health-dashboard-header">
              <strong>{t(locale, "obsDlqTitle")}</strong>
              <button
                type="button"
                className="secondary compact"
                disabled={!connected || busy || snapshot.dlqRuns.length === 0}
                onClick={() => void replayAll()}
              >
                {busy ? t(locale, "obsDlqReplaying") : t(locale, "obsDlqReplayAll")}
              </button>
            </div>
            {snapshot.dlqRuns.length === 0 ? (
              <p className="hint muted">{t(locale, "obsDlqEmpty")}</p>
            ) : (
              <ul className="dlq-list">
                {snapshot.dlqRuns.map((run) => (
                  <li key={run.run_id}>
                    <span className="dlq-run-id" title={run.input}>
                      {run.run_id.slice(0, 8)}…
                    </span>
                    <span className="hint muted">{run.updated_at?.slice(0, 19) ?? "—"}</span>
                    <button
                      type="button"
                      className="secondary compact"
                      disabled={!connected || busy}
                      onClick={() => void replayOne(run.run_id)}
                    >
                      {t(locale, "obsDlqReplayOne")}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : (
        <p className="hint muted">{connected ? "…" : "—"}</p>
      )}
    </div>
  );
}
