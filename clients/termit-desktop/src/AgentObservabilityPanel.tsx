import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
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
}

export function AgentObservabilityPanel({ client, connected, locale }: AgentObservabilityPanelProps) {
  const [snapshot, setSnapshot] = useState<OpsSnapshot | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const [metrics, evalDash] = await Promise.all([
        client.getAgentRunsMetrics(),
        client.getEvalDashboard(1),
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
      ) : (
        <p className="hint muted">{connected ? "…" : "—"}</p>
      )}
    </div>
  );
}
