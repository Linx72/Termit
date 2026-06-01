import { useCallback, useEffect, useState } from "react";
import type { AgentRunRecord, TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface DlqPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
  onReplayed?: (runIds: string[]) => void;
}

export function DlqPanel({ client, connected, locale, onReplayed }: DlqPanelProps) {
  const [runs, setRuns] = useState<AgentRunRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const response = await client.listDlqRuns(20);
      setRuns(response.runs);
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

  const replayOne = async (runId: string) => {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const created = await client.replayAgentRun(runId);
      setStatus(`${t(locale, "dlqReplayed")}: ${created.run_id.slice(0, 8)}…`);
      onReplayed?.([created.run_id]);
      await refresh();
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    } finally {
      setBusy(false);
    }
  };

  const replayBatch = async () => {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const response = await client.replayDlqRuns(5);
      const ids = response.replayed.map((item) => item.run_id);
      setStatus(`${t(locale, "dlqReplayed")}: ${response.count}`);
      onReplayed?.(ids);
      await refresh();
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="dlq-panel" aria-label={t(locale, "dlqTitle")}>
      <div className="health-dashboard-header">
        <strong>{t(locale, "dlqTitle")}</strong>
        <span className="hint muted">{runs.length}</span>
        <button
          type="button"
          className="secondary compact"
          disabled={!connected || busy}
          onClick={() => void refresh()}
        >
          ↻
        </button>
      </div>
      {error && <p className="hint error-text">{error}</p>}
      {status && <p className="hint muted">{status}</p>}
      {runs.length > 0 ? (
        <>
          <ul className="dlq-list">
            {runs.slice(0, 8).map((run) => (
              <li key={run.run_id} className="dlq-item">
                <span className="dlq-run-id" title={run.run_id}>
                  {run.run_id.slice(0, 8)}…
                </span>
                <span className="hint muted">{run.agent_name || run.agent_id}</span>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={!connected || busy}
                  onClick={() => void replayOne(run.run_id)}
                >
                  {t(locale, "dlqReplayOne")}
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="secondary compact"
            disabled={!connected || busy}
            onClick={() => void replayBatch()}
          >
            {t(locale, "dlqReplayBatch")}
          </button>
        </>
      ) : (
        <p className="hint muted">{connected ? t(locale, "dlqEmpty") : "—"}</p>
      )}
    </div>
  );
}
