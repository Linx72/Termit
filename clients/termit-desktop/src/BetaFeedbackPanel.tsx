import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { getBetaMetrics, submitFeedback, type BetaMetrics } from "@termit/client";
import { getBetaActorId } from "./betaActivity";
import { t, type Locale } from "./i18n";

interface BetaFeedbackPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

export function BetaFeedbackPanel({ client, connected, locale }: BetaFeedbackPanelProps) {
  const [message, setMessage] = useState("");
  const [rating, setRating] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [metrics, setMetrics] = useState<BetaMetrics | null>(null);

  const refreshMetrics = useCallback(async () => {
    if (!connected) {
      return;
    }
    try {
      const payload = await getBetaMetrics(client);
      setMetrics(payload);
    } catch {
      setMetrics(null);
    }
  }, [client, connected]);

  useEffect(() => {
    void refreshMetrics();
  }, [refreshMetrics]);

  const onSubmit = async () => {
    if (!message.trim()) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await submitFeedback(client, {
        message: message.trim(),
        rating,
        session_id: getBetaActorId(),
      });
      setNotice(`${t(locale, "betaFeedbackSent")}: ${result.timestamp}`);
      setMessage("");
      await refreshMetrics();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="beta-feedback-panel" id="beta-invite-panel">
      <strong>{t(locale, "betaFeedbackTitle")}</strong>
      <p className="hint">{t(locale, "betaFeedbackHint")}</p>
      {metrics ? (
        <p className="hint muted">
          D30:{" "}
          {metrics.d30_retention_rate != null
            ? `${Math.round(metrics.d30_retention_rate * 100)}% (${metrics.retained_d30}/${metrics.cohort_size_d30})`
            : "—"}{" "}
          · {t(locale, "betaFeedbackTotal")}: {metrics.feedback_total}
        </p>
      ) : null}
      {error ? <p className="hint error-text">{error}</p> : null}
      {notice ? <p className="hint ok-text">{notice}</p> : null}
      {!connected ? <p className="hint">{t(locale, "mediaStudioConnectFirst")}</p> : null}
      {connected ? (
        <>
          <div className="field">
            <label htmlFor="betaFeedbackRating">{t(locale, "betaFeedbackRating")}</label>
            <select
              id="betaFeedbackRating"
              value={rating}
              onChange={(e) => setRating(Number(e.target.value))}
            >
              {[5, 4, 3, 2, 1].map((value) => (
                <option key={value} value={value}>
                  {value}/5
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="betaFeedbackMessage">{t(locale, "betaFeedbackMessage")}</label>
            <textarea
              id="betaFeedbackMessage"
              rows={3}
              value={message}
              placeholder={t(locale, "betaFeedbackPlaceholder")}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>
          <button type="button" className="secondary compact" disabled={busy} onClick={() => void onSubmit()}>
            {t(locale, "betaFeedbackSubmit")}
          </button>
        </>
      ) : null}
    </div>
  );
}
