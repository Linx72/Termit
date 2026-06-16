import { useCallback, useEffect, useState } from "react";
import type { QuotaEntrySummary, TermitClient, ToolAuditEvent } from "@termit/client";
import { t, type Locale } from "./i18n";

interface OpsSecurityPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

interface SecuritySnapshot {
  authEnabled: boolean;
  quotaEntries: QuotaEntrySummary[];
  retryAttempts: number | null;
  retryBackoffMs: number | null;
  shutdownGraceSeconds: number | null;
}

export function OpsSecurityPanel({ client, connected, locale }: OpsSecurityPanelProps) {
  const [snapshot, setSnapshot] = useState<SecuritySnapshot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const [quota, policy] = await Promise.all([
        client.getQuotaSummary(),
        client.getRuntimePolicy(),
      ]);
      setSnapshot({
        authEnabled: quota.auth_enabled,
        quotaEntries: quota.entries ?? [],
        retryAttempts: policy.run_max_attempts,
        retryBackoffMs: policy.run_retry_backoff_ms,
        shutdownGraceSeconds: policy.shutdown_grace_seconds,
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

  const exportAudit = async () => {
    if (!connected || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const events: ToolAuditEvent[] = await client.getToolAudit(200);
      const blob = new Blob([JSON.stringify(events, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `termit-tool-audit-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ops-security-panel" aria-label={t(locale, "opsSecurityTitle")}>
      <div className="health-dashboard-header">
        <strong>{t(locale, "opsSecurityTitle")}</strong>
        <button type="button" className="secondary compact" disabled={!connected} onClick={() => void refresh()}>
          ↻
        </button>
      </div>
      {error ? <p className="hint error-text">{error}</p> : null}
      {snapshot ? (
        <>
          {!snapshot.authEnabled ? (
            <p className="hint muted">{t(locale, "opsAuthDisabled")}</p>
          ) : snapshot.quotaEntries.length === 0 ? (
            <p className="hint muted">{t(locale, "opsQuotaEmpty")}</p>
          ) : (
            <ul className="quota-list">
              {snapshot.quotaEntries.map((entry) => (
                <li key={entry.key_hint}>
                  <span className="quota-key">{entry.key_hint}</span>
                  <span className="hint muted">
                    {entry.role} · {entry.team}
                  </span>
                  <span>
                    {entry.used}/{entry.limit} ({entry.usage_percent.toFixed(0)}%)
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="hint muted">
            {t(locale, "opsRetryPolicy")}: {snapshot.retryAttempts ?? "—"} attempts · backoff{" "}
            {snapshot.retryBackoffMs ?? "—"}ms · shutdown grace {snapshot.shutdownGraceSeconds ?? "—"}s
          </p>
          <button
            type="button"
            className="secondary compact"
            disabled={!connected || busy}
            onClick={() => void exportAudit()}
          >
            {busy ? t(locale, "opsExporting") : t(locale, "opsExportAudit")}
          </button>
        </>
      ) : (
        <p className="hint muted">{connected ? "…" : "—"}</p>
      )}
    </div>
  );
}
