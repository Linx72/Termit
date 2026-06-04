import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import {
  getAutomationPrefs,
  updateAutomationPrefs,
  type AutomationPrefsResponse,
  type AutomationToggleItem,
} from "@termit/client";
import { t, type Locale } from "./i18n";

interface AutomationPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

function toggleLabel(item: AutomationToggleItem, locale: Locale): string {
  return locale === "ru" ? item.label_ru : item.label_en;
}

function toggleDescription(item: AutomationToggleItem, locale: Locale): string {
  return locale === "ru" ? item.description_ru : item.description_en;
}

export function AutomationPanel({ client, connected, locale }: AutomationPanelProps) {
  const [open, setOpen] = useState(false);
  const [prefs, setPrefs] = useState<AutomationPrefsResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const response = await getAutomationPrefs(client);
      setPrefs(response);
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    }
  }, [client, connected]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const applyMaster = async (enabled: boolean) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await updateAutomationPrefs(client, { automatic_mode_enabled: enabled });
      setPrefs(response);
      setNotice(
        enabled ? t(locale, "automationEnabledNotice") : t(locale, "automationDisabledNotice"),
      );
      if (response.restart_recommended) {
        setNotice((prev) => `${prev} ${t(locale, "automationRestartHint")}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const applyToggle = async (toggleId: string, enabled: boolean) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await updateAutomationPrefs(client, { toggles: { [toggleId]: enabled } });
      setPrefs(response);
      if (response.restart_recommended) {
        setNotice(t(locale, "automationRestartHint"));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="automation-panel">
      <button
        type="button"
        className="secondary compact setup-guide-toggle"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? t(locale, "automationPanelHide") : t(locale, "automationPanelShow")}
      </button>
      {open ? (
        <div className="setup-guide-body">
          <strong>{t(locale, "automationPanelTitle")}</strong>
          <p className="hint">{t(locale, "automationPanelHint")}</p>
          {error ? <p className="hint error-text">{error}</p> : null}
          {notice ? <p className="hint ok-text">{notice}</p> : null}
          {!connected ? <p className="hint">{t(locale, "automationConnectFirst")}</p> : null}
          {connected && prefs ? (
            <>
              <div className="automation-master-row">
                <span className={`health-tag ${prefs.automatic_mode_enabled ? "ok" : "bad"}`}>
                  {prefs.automatic_mode_enabled
                    ? t(locale, "automationMasterOn")
                    : t(locale, "automationMasterOff")}
                </span>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={busy}
                  onClick={() => void applyMaster(!prefs.automatic_mode_enabled)}
                >
                  {prefs.automatic_mode_enabled
                    ? t(locale, "automationDisableAll")
                    : t(locale, "automationEnableAll")}
                </button>
                <button type="button" className="secondary compact" disabled={busy} onClick={() => void refresh()}>
                  ↻
                </button>
              </div>
              <ul className="automation-toggle-list">
                {prefs.toggles.map((item) => (
                  <li key={item.toggle_id}>
                    <label className="checkbox-row automation-toggle-row">
                      <input
                        type="checkbox"
                        checked={item.enabled}
                        disabled={busy || !connected}
                        onChange={(event) => void applyToggle(item.toggle_id, event.target.checked)}
                      />
                      <span>
                        <strong>{toggleLabel(item, locale)}</strong>
                        <span className="hint block-hint">{toggleDescription(item, locale)}</span>
                        {item.requires_restart ? (
                          <span className="hint block-hint">{t(locale, "automationRequiresRestart")}</span>
                        ) : null}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              <p className="hint mono-hint">{prefs.env_path}</p>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
