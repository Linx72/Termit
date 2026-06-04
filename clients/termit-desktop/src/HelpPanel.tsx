import { useCallback, useEffect, useState } from "react";
import { t, type Locale } from "./i18n";

export type DocId = "help" | "training";

interface HelpPanelProps {
  locale: Locale;
  onOpenTab?: () => void;
}

export function HelpPanel({ locale }: HelpPanelProps) {
  const [activeDoc, setActiveDoc] = useState<DocId>("help");
  const [fileUrl, setFileUrl] = useState("");
  const [filePath, setFilePath] = useState("");
  const [status, setStatus] = useState("");

  const loadDoc = useCallback(async (docId: DocId) => {
    setActiveDoc(docId);
    try {
      const [url, path] = await Promise.all([
        window.termitDesktop.getDocFileUrl(docId),
        window.termitDesktop.getDocPath(docId),
      ]);
      setFileUrl(url);
      setFilePath(path);
      setStatus("");
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    }
  }, []);

  useEffect(() => {
    void loadDoc("help");
  }, [loadDoc]);

  const openExternal = async (docId: DocId) => {
    const result = await window.termitDesktop.openDocExternal(docId);
    setStatus(result.ok ? t(locale, "docOpenedExternal") : result.message);
  };

  return (
    <div className="help-panel">
      <header className="help-header">
        <h2>{t(locale, "helpSectionTitle")}</h2>
        <p className="hint">{t(locale, "helpSectionIntro")}</p>
      </header>

      <nav className="help-nav chips">
        <button
          type="button"
          className={`chip secondary compact ${activeDoc === "help" ? "active" : ""}`}
          onClick={() => void loadDoc("help")}
        >
          {t(locale, "helpDocTitle")}
        </button>
        <button
          type="button"
          className={`chip secondary compact ${activeDoc === "training" ? "active" : ""}`}
          onClick={() => void loadDoc("training")}
        >
          {t(locale, "trainingDocTitle")}
        </button>
      </nav>

      <div className="help-actions row">
        <button type="button" className="primary compact" onClick={() => void openExternal(activeDoc)}>
          {t(locale, "openDocExternal")}
        </button>
        <button type="button" className="secondary compact" onClick={() => void loadDoc(activeDoc)}>
          {t(locale, "refreshDocPreview")}
        </button>
      </div>

      {filePath ? (
        <p className="hint doc-path">
          {t(locale, "docLocalPath")}: <code>{filePath}</code>
        </p>
      ) : null}

      {status ? <p className="hint">{status}</p> : null}

      <section className="help-doc-section">
        <h3>{activeDoc === "help" ? t(locale, "helpDocTitle") : t(locale, "trainingDocTitle")}</h3>
        <p className="hint">
          {activeDoc === "help" ? t(locale, "helpDocDesc") : t(locale, "trainingDocDesc")}
        </p>
        {fileUrl ? (
          <iframe
            className="doc-frame"
            title={activeDoc === "help" ? t(locale, "helpDocTitle") : t(locale, "trainingDocTitle")}
            src={fileUrl}
          />
        ) : (
          <div className="message-block meta">{t(locale, "docLoading")}</div>
        )}
      </section>

      <section className="help-links">
        <h4>{t(locale, "helpRelatedLinks")}</h4>
        <ul className="setup-steps">
          <li>
            <button type="button" className="linkish" onClick={() => void loadDoc("help")}>
              {t(locale, "helpLinkHelpPdf")}
            </button>
          </li>
          <li>
            <button type="button" className="linkish" onClick={() => void loadDoc("training")}>
              {t(locale, "helpLinkTrainingPdf")}
            </button>
          </li>
          <li>
            <button type="button" className="linkish" onClick={() => void openExternal("help")}>
              {t(locale, "helpLinkOpenHelpOs")}
            </button>
          </li>
          <li>
            <button type="button" className="linkish" onClick={() => void openExternal("training")}>
              {t(locale, "helpLinkOpenTrainingOs")}
            </button>
          </li>
        </ul>
      </section>
    </div>
  );
}
