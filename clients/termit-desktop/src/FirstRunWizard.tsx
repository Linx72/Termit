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
  onPullModel: (model: string) => void | Promise<void>;
  onComplete: () => void;
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
  onPullModel,
  onComplete,
}: FirstRunWizardProps) {
  const canFinish = Boolean(settings.repoRoot && settings.workspace && settings.baseUrl);

  return (
    <div className="modal-backdrop wizard-backdrop" role="presentation">
      <div className="modal wizard-modal" role="dialog" aria-labelledby="first-run-title">
        <h2 id="first-run-title">
          {locale === "ru" ? "Добро пожаловать в Termit" : "Welcome to Termit"}
        </h2>
        <p className="hint">
          {locale === "ru"
            ? "Первый запуск: API → Ollama → workspace → Connect."
            : "First run: API → Ollama → workspace → Connect."}
        </p>

        <div className="field">
          <label htmlFor="wizard-baseUrl">URL API Termit</label>
          <input
            id="wizard-baseUrl"
            value={settings.baseUrl}
            onChange={(event) => onUpdate({ baseUrl: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="wizard-repo">{locale === "ru" ? "Репозиторий Termit" : "Termit repo"}</label>
          <input id="wizard-repo" value={settings.repoRoot} readOnly placeholder="/path/to/Termit" />
          <button type="button" className="secondary" onClick={() => void onPickRepo()}>
            {locale === "ru" ? "Выбрать repo" : "Choose repo"}
          </button>
        </div>

        <div className="field">
          <label htmlFor="wizard-workspace">Workspace</label>
          <input id="wizard-workspace" value={settings.workspace} readOnly />
          <button type="button" className="secondary" onClick={() => void onPickWorkspace()}>
            {locale === "ru" ? "Выбрать папку" : "Choose folder"}
          </button>
        </div>

        <div className="wizard-section">
          <h3>{t(locale, "wizardOllama")}</h3>
          <p className="hint">{t(locale, "wizardOllamaHint")}</p>
          {missingOllamaModels.length === 0 ? (
            <p className="hint muted">Ollama models: OK</p>
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
            checked={settings.autoConnect}
            onChange={(event) => onUpdate({ autoConnect: event.target.checked })}
          />
          {locale === "ru" ? "Подключаться при запуске" : "Connect on launch"}
        </label>

        <div className="row">
          <button type="button" className="primary" disabled={busy} onClick={() => void onConnect()}>
            {t(locale, "connect")}
          </button>
        </div>

        {healthLine && <pre className="detail-box wizard-health">{healthLine}</pre>}

        <div className="row">
          <button type="button" className="primary" disabled={!canFinish} onClick={onComplete}>
            {locale === "ru" ? "Начать работу" : "Get started"}
          </button>
        </div>
      </div>
    </div>
  );
}
