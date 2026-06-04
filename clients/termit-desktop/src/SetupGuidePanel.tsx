import { useState } from "react";
import { t, type Locale } from "./i18n";

interface SetupGuidePanelProps {
  locale: Locale;
  defaultOpen?: boolean;
  onOpenHelp?: () => void;
}

export function SetupGuidePanel({ locale, defaultOpen = true, onOpenHelp }: SetupGuidePanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="setup-guide">
      <button
        type="button"
        className="secondary compact setup-guide-toggle"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? t(locale, "setupGuideHide") : t(locale, "setupGuideToggle")}
      </button>
      {open ? (
        <div className="setup-guide-body">
          <strong>{t(locale, "setupGuideTitle")}</strong>

          <section>
            <h4>{t(locale, "setupWhatTitle")}</h4>
            <p className="hint">{t(locale, "setupWhatBody")}</p>
          </section>

          <section>
            <h4>{t(locale, "setupStepsTitle")}</h4>
            <ol className="setup-steps">
              <li>{t(locale, "setupStep1")}</li>
              <li>{t(locale, "setupStep2")}</li>
              <li>{t(locale, "setupStep3")}</li>
              <li>{t(locale, "setupStep4")}</li>
              <li>{t(locale, "setupStep5")}</li>
            </ol>
          </section>

          <section>
            <h4>{t(locale, "setupAutoTitle")}</h4>
            <p className="hint">{t(locale, "setupAutoBody")}</p>
          </section>

          <section>
            <h4>{t(locale, "setupLangTitle")}</h4>
            <p className="hint">{t(locale, "setupLangBody")}</p>
          </section>

          {onOpenHelp ? (
            <button type="button" className="primary compact" onClick={onOpenHelp}>
              {t(locale, "openHelpTab")}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
