import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { getDesktopKpiGates, type DesktopKpiGateResponse } from "@termit/client";
import { t, type Locale } from "./i18n";

interface KpiGatePanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

function formatRate(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function formatGateValue(gate: { gate_id: string; actual: number; target: number }): string {
  if (gate.gate_id.includes("_ms") || gate.gate_id.endsWith("_ms")) {
    return `${gate.actual.toFixed(0)}ms / ${gate.target.toFixed(0)}ms`;
  }
  if (gate.gate_id.includes("seconds") || gate.gate_id === "ttfuc_seconds") {
    return `${gate.actual.toFixed(0)}s / ${gate.target.toFixed(0)}s`;
  }
  return `${formatRate(gate.actual)} / ${formatRate(gate.target)}`;
}

export function KpiGatePanel({ client, connected, locale }: KpiGatePanelProps) {
  const [payload, setPayload] = useState<DesktopKpiGateResponse | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const response = await getDesktopKpiGates(client);
      setPayload(response);
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    }
  }, [client, connected]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="kpi-gate-panel">
      <div className="health-dashboard-header">
        <strong>{t(locale, "kpiGateTitle")}</strong>
        <button type="button" className="secondary compact" disabled={!connected} onClick={() => void refresh()}>
          ↻
        </button>
      </div>
      {error ? <p className="hint error-text">{error}</p> : null}
      {payload ? (
        <>
          <p className={`health-tag ${payload.overall_passed ? "ok" : "bad"}`}>
            {payload.overall_passed ? t(locale, "kpiGatePassed") : t(locale, "kpiGateFailed")} ·{" "}
            {payload.passed_count}/{payload.total_gates}
          </p>
          <ul className="health-stats">
            {payload.gates.map((gate) => (
              <li key={gate.gate_id}>
                <span className={`health-dot ${gate.passed ? "ok" : "bad"}`} />
                {gate.label}: {formatGateValue(gate)}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="hint muted">{connected ? "…" : "—"}</p>
      )}
    </div>
  );
}
