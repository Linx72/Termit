import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface AssignmentRow {
  assignment_id: string;
  root_path: string;
  brief_path: string;
  deliverables_path: string;
}

interface AssignmentsPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
  onStatus?: (message: string) => void;
}

export function AssignmentsPanel({
  client,
  connected,
  locale,
  onStatus,
}: AssignmentsPanelProps) {
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [criteria, setCriteria] = useState("");
  const [rows, setRows] = useState<AssignmentRow[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    try {
      const list = await client.listAssignments(30);
      setRows(list);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      onStatus?.(text);
    }
  }, [client, connected, onStatus]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createAssignment = async () => {
    if (!connected || busy || brief.trim().length < 10) {
      return;
    }
    setBusy(true);
    try {
      const created = await client.createAssignment({
        title: title.trim() || "Web project",
        brief: brief.trim(),
        success_criteria: criteria
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
        target_urls: [],
      });
      onStatus?.(`${t(locale, "assignmentCreated")}: ${created.assignment_id}`);
      setTitle("");
      setBrief("");
      setCriteria("");
      await refresh();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      onStatus?.(text);
    } finally {
      setBusy(false);
    }
  };

  const seedWebAgent = async (templateId: string) => {
    if (!connected || busy) {
      return;
    }
    setBusy(true);
    try {
      const agent = await client.ensureAgentFromTemplate(templateId);
      onStatus?.(`${t(locale, "agentReady")}: ${agent.name} (${agent.agent_id})`);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      onStatus?.(text);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-body assignments-panel">
      <p className="hint">{t(locale, "assignmentsHint")}</p>
      <div className="stack">
        <label>
          {t(locale, "assignmentTitle")}
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t(locale, "assignmentTitlePlaceholder")} />
        </label>
        <label>
          {t(locale, "assignmentBrief")}
          <textarea
            rows={5}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder={t(locale, "assignmentBriefPlaceholder")}
          />
        </label>
        <label>
          {t(locale, "assignmentCriteria")}
          <textarea
            rows={3}
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
            placeholder={t(locale, "assignmentCriteriaPlaceholder")}
          />
        </label>
        <div className="row">
          <button type="button" disabled={!connected || busy} onClick={() => void createAssignment()}>
            {t(locale, "assignmentCreate")}
          </button>
          <button type="button" className="secondary" disabled={!connected || busy} onClick={() => void refresh()}>
            {t(locale, "refresh")}
          </button>
        </div>
        <div className="row">
          <button
            type="button"
            className="secondary compact"
            disabled={!connected || busy}
            onClick={() => void seedWebAgent("web-app-vite")}
          >
            {t(locale, "seedWebAppAgent")}
          </button>
          <button
            type="button"
            className="secondary compact"
            disabled={!connected || busy}
            onClick={() => void seedWebAgent("online-project-manager")}
          >
            {t(locale, "seedOnlineAgent")}
          </button>
        </div>
      </div>
      <h3>{t(locale, "assignmentList")}</h3>
      <ul className="assignment-list">
        {rows.map((row) => (
          <li key={row.assignment_id}>
            <strong>{row.assignment_id}</strong>
            <div className="muted">{row.root_path}</div>
          </li>
        ))}
      </ul>
      {rows.length === 0 && <p className="muted">{t(locale, "assignmentEmpty")}</p>}
    </div>
  );
}
