import type { StoredSettings } from "./settings";
import { t, type Locale } from "./i18n";

interface FirstRunWizardProps {
  settings: StoredSettings;
  healthLine: string;
  busy: boolean;
  locale: Locale;
  missingOllamaModels: string[];
  pullingModel: string | null;
  onUpdate: (patch: Partial<StoredSettings>) => void;
  onPickRepo: () => void | Promise<void>;
  onPickWorkspace: () => void | Promise<void>;
  onConnect: () => void | Promise<void>;
  onToggleAutoStartServer: (enabled: boolean) => void | Promise<void>;
  onPullModel: (model: string) => void | Promise<void>;
  onComplete: () => void | Promise<void>;
}

export function FirstRunWizard({
  settings,
  healthLine,
  busy,
  locale,
  missingOllamaModels,
  pullingModel,
  onUpdate,
  onPickRepo,
  onPickWorkspace,
  onConnect,
  onToggleAutoStartServer,
  onPullModel,
  onComplete,
}: FirstRunWizardProps) {
  const canFinish = Boolean(settings.baseUrl.trim() && settings.workspace.trim());

  return (
    <div className="modal-backdrop wizard-backdrop" role="presentation">
      <div className="modal wizard-modal" role="dialog" aria-labelledby="first-run-title">
        <h2 id="first-run-title">{t(locale, "wizardTitle")}</h2>
        <p className="hint">{t(locale, "wizardIntro")}</p>

        <div className="field">
          <label htmlFor="wizard-baseUrl">{t(locale, "wizardApiUrl")}</label>
          <input
            id="wizard-baseUrl"
            value={settings.baseUrl}
            onChange={(event) => onUpdate({ baseUrl: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="wizard-repo">{t(locale, "wizardRepo")}</label>
          <input id="wizard-repo" value={settings.repoRoot} readOnly placeholder="/path/to/Termit" />
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void onPickRepo()}
          >
            {t(locale, "wizardChooseRepo")}
          </button>
        </div>

        <div className="field">
          <label htmlFor="wizard-workspace">{t(locale, "wizardWorkspace")}</label>
          <input id="wizard-workspace" value={settings.workspace} readOnly />
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void onPickWorkspace()}
          >
            {t(locale, "wizardChooseFolder")}
          </button>
        </div>

        <div className="wizard-section">
          <h3>{t(locale, "wizardOllama")}</h3>
          <p className="hint">{t(locale, "wizardOllamaHint")}</p>
          {missingOllamaModels.length === 0 ? (
            <p className="hint muted">{t(locale, "wizardOllamaOk")}</p>
          ) : (
            <ul className="wizard-model-list">
              {missingOllamaModels.map((model) => (
                <li key={model}>
                  {model}
                  <button
                    type="button"
                    className="secondary compact"
                    disabled={busy || pullingModel === model}
                    onClick={() => void onPullModel(model)}
                  >
                    {pullingModel === model ? "…" : t(locale, "pullModel")}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoStartServer}
            disabled={settings.runtimeMode === "web"}
            onChange={(event) => void onToggleAutoStartServer(event.target.checked)}
          />
          {t(locale, "wizardAutoStartServer")}
        </label>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoConnect}
            onChange={(event) => onUpdate({ autoConnect: event.target.checked })}
          />
          {t(locale, "wizardConnectOnLaunch")}
        </label>

        <div className="row">
          <button type="button" className="primary" disabled={busy} onClick={() => void onConnect()}>
            {t(locale, "connect")}
          </button>
        </div>

        {healthLine && <pre className="detail-box wizard-health">{healthLine}</pre>}

        <div className="row">
          <button
            type="button"
            className="primary"
            disabled={!canFinish || busy}
            onClick={() => {
              if (!canFinish) {
                return;
              }
              void onComplete();
            }}
          >
            {t(locale, "wizardGetStarted")}
          </button>
        </div>
      </div>
    </div>
  );
}
