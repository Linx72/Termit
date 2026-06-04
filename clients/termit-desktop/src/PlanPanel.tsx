import { useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface PlanPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
  sessionId: string;
  selectedModel: string;
  repoProfile: string;
  projectId: string;
  onSessionId: (id: string) => void;
  onBuild: (planText: string) => void;
  onBuildAndVerify: (planText: string) => void;
}

type PlanBlock =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string }
  | { id: string; kind: "error"; text: string };

const PLAN_PREFIX =
  "[PLAN MODE] Produce a step-by-step implementation plan only. Do not write code, patches, or shell commands.\n\nTask:\n";

function blockId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function PlanPanel({
  client,
  connected,
  locale,
  sessionId,
  selectedModel,
  repoProfile,
  projectId,
  onSessionId,
  onBuild,
  onBuildAndVerify,
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
      for await (const event of client.chatStream({
        message: `${PLAN_PREFIX}${message}`,
        task_type: "general",
        session_id: sessionId || undefined,
        model: selectedModel || undefined,
        repo_profile: repoProfile || undefined,
        use_retrieval: true,
        use_repo_map: Boolean(projectId),
        project_id: projectId || undefined,
      })) {
        if (event.event === "meta") {
          const next = String(event.data.session_id ?? "");
          if (next) {
            onSessionId(next);
          }
        } else if (event.event === "token") {
          response += String(event.data.text ?? "");
          setBlocks((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.kind !== "assistant") {
              return prev;
            }
            return [...prev.slice(0, -1), { ...last, text: last.text + String(event.data.text ?? "") }];
          });
        }
      }
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
      <h3>{t(locale, "planTitle")}</h3>
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
        <button type="button" className="primary" disabled={!connected || busy || !draft.trim()} onClick={() => void sendPlan()}>
          {t(locale, "planButton")}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={!lastAssistant.trim()}
          onClick={() => onBuild(lastAssistant.trim())}
        >
          {t(locale, "build")}
        </button>
        <button
          type="button"
          className="primary"
          disabled={!lastAssistant.trim()}
          onClick={() => onBuildAndVerify(lastAssistant.trim())}
        >
          {t(locale, "buildAndVerify")}
        </button>
      </div>
    </div>
  );
}
