import type { StoredSettings } from "./settings";

interface FirstRunWizardProps {
  settings: StoredSettings;
  healthLine: string;
  busy: boolean;
  onUpdate: (patch: Partial<StoredSettings>) => void;
  onPickRepo: () => void | Promise<void>;
  onPickWorkspace: () => void | Promise<void>;
  onConnect: () => void | Promise<void>;
  onComplete: () => void;
}

export function FirstRunWizard({
  settings,
  healthLine,
  busy,
  onUpdate,
  onPickRepo,
  onPickWorkspace,
  onConnect,
  onComplete,
}: FirstRunWizardProps) {
  const canFinish = Boolean(settings.repoRoot && settings.workspace && settings.baseUrl);

  return (
    <div className="modal-backdrop wizard-backdrop" role="presentation">
      <div className="modal wizard-modal" role="dialog" aria-labelledby="first-run-title">
        <h2 id="first-run-title">Добро пожаловать в Termit</h2>
        <p className="hint">
          Первый запуск: укажите пути и подключитесь к API. Сервер по умолчанию — LaunchAgent
          (<code>./scripts/install_launch_agent.sh</code>).
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
          <label htmlFor="wizard-repo">Репозиторий Termit</label>
          <input id="wizard-repo" value={settings.repoRoot} readOnly placeholder="/path/to/Termit" />
          <button type="button" className="secondary" onClick={() => void onPickRepo()}>
            Выбрать repo
          </button>
        </div>

        <div className="field">
          <label htmlFor="wizard-workspace">Workspace (ваш код)</label>
          <input id="wizard-workspace" value={settings.workspace} readOnly />
          <button type="button" className="secondary" onClick={() => void onPickWorkspace()}>
            Выбрать папку
          </button>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoConnect}
            onChange={(event) => onUpdate({ autoConnect: event.target.checked })}
          />
          Подключаться при запуске
        </label>

        <div className="row">
          <button type="button" className="primary" disabled={busy} onClick={() => void onConnect()}>
            Подключить
          </button>
        </div>

        {healthLine && <pre className="detail-box wizard-health">{healthLine}</pre>}

        <div className="row">
          <button
            type="button"
            className="primary"
            disabled={!canFinish}
            onClick={onComplete}
          >
            Начать работу
          </button>
        </div>
      </div>
    </div>
  );
}
