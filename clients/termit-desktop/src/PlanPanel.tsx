import { useState } from "react";
import { t, type Locale } from "./i18n";

interface PlanPanelProps {
  locale: Locale;
  connected: boolean;
  onRunPlan: (message: string) => Promise<{ response: string; sessionId?: string }>;
  onBuild: (planText: string) => void;
  onBuildAndVerify: (planText: string) => void;
  externalBusy?: boolean;
  modeLabel?: string;
}

type PlanBlock =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string }
  | { id: string; kind: "error"; text: string };

function blockId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function PlanPanel({
  locale,
  connected,
  onRunPlan,
  onBuild,
  onBuildAndVerify,
  externalBusy = false,
  modeLabel,
}: PlanPanelProps) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [blocks, setBlocks] = useState<PlanBlock[]>([]);

  const lastAssistant = [...blocks].reverse().find((block) => block.kind === "assistant")?.text ?? "";

  const sendPlan = async () => {
    const message = draft.trim();
    if (!message || !connected || busy) {
      return;
    }
    setDraft("");
    setBusy(true);
    setBlocks((prev) => [
      ...prev,
      { id: blockId(), kind: "user", text: message },
      { id: blockId(), kind: "assistant", text: "" },
    ]);
    try {
      let response = "";
      const run = await onRunPlan(message);
      response = run.response ?? "";
      setBlocks((prev) => {
        const last = prev[prev.length - 1];
        if (!last || last.kind !== "assistant") {
          return prev;
        }
        return [...prev.slice(0, -1), { ...last, text: response }];
      });
      if (!response.trim()) {
        setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text: t(locale, "planEmptyResponse") }]);
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-body plan-panel">
      <div className="row">
        <h3>{t(locale, "planTitle")}</h3>
        {modeLabel ? <span className="cursor-mode-badge">{modeLabel}</span> : null}
      </div>
      <p className="hint">{t(locale, "planHint")}</p>
      <div className="chat-log plan-log">
        {blocks.length === 0 ? (
          <div className="message-block meta">{t(locale, "planEmptyHint")}</div>
        ) : (
          blocks.map((block) => (
            <div key={block.id} className={`message-block ${block.kind}`}>
              {block.text}
            </div>
          ))
        )}
      </div>
      <textarea
        value={draft}
        placeholder={t(locale, "planInputPlaceholder")}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            void sendPlan();
          }
        }}
      />
      <div className="row">
        <button type="button" className="primary" disabled={!connected || busy || externalBusy || !draft.trim()} onClick={() => void sendPlan()}>
          {t(locale, "planButton")}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={!lastAssistant.trim() || busy || externalBusy}
          onClick={() => onBuild(lastAssistant.trim())}
        >
          {t(locale, "build")}
        </button>
        <button
          type="button"
          className="primary"
          disabled={!lastAssistant.trim() || busy || externalBusy}
          onClick={() => onBuildAndVerify(lastAssistant.trim())}
        >
          {t(locale, "buildAndVerify")}
        </button>
      </div>
    </div>
  );
}
