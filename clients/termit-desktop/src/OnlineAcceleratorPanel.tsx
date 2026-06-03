import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import {
  enqueueHeavyJob,
  getHeavyJob,
  listHeavyJobs,
  listSharedRuns,
  shareAgentRun,
  type DesktopHeavyJob,
  type DesktopSharedRun,
} from "@termit/client";
import { t, type Locale } from "./i18n";

interface OnlineAcceleratorPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
  watchedRunId: string | null;
  team: string;
  onTeamChange: (team: string) => void;
}

export function OnlineAcceleratorPanel({
  client,
  connected,
  locale,
  watchedRunId,
  team,
  onTeamChange,
}: OnlineAcceleratorPanelProps) {
  const [sharedRuns, setSharedRuns] = useState<DesktopSharedRun[]>([]);
  const [jobs, setJobs] = useState<DesktopHeavyJob[]>([]);
  const [status, setStatus] = useState("");
  const [shareNote, setShareNote] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    try {
      const [shared, heavy] = await Promise.all([
        listSharedRuns(client, { limit: 20, team: team || undefined }),
        listHeavyJobs(client, 10),
      ]);
      setSharedRuns(shared.shared_runs);
      setJobs(heavy.jobs);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    }
  }, [client, connected, team]);

  useEffect(() => {
    void refresh();
    if (!connected) {
      return;
    }
    const timer = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(timer);
  }, [connected, refresh]);

  const shareCurrentRun = async () => {
    if (!watchedRunId) {
      setStatus(locale === "ru" ? "Выберите run в Agents." : "Select a run in Agents tab.");
      return;
    }
    setBusy(true);
    try {
      await shareAgentRun(client, {
        run_id: watchedRunId,
        team: team || "default",
        note: shareNote,
        shared_by: "desktop",
      });
      setShareNote("");
      setStatus(locale === "ru" ? "Run опубликован." : "Run shared.");
      await refresh();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    } finally {
      setBusy(false);
    }
  };

  const startEvalJob = async () => {
    setBusy(true);
    try {
      const job = await enqueueHeavyJob(client, {
        job_type: "eval_suite",
        payload: { category: "local", limit: 5 },
        requested_by: "desktop",
      });
      setStatus(`${locale === "ru" ? "Heavy job" : "Heavy job"}: ${job.job_id} (${job.state})`);
      await refresh();
      window.setTimeout(async () => {
        try {
          const latest = await getHeavyJob(client, job.job_id);
          setStatus(`${latest.job_id}: ${latest.state}${latest.error ? ` · ${latest.error}` : ""}`);
          await refresh();
        } catch {
          /* ignore poll errors */
        }
      }, 2500);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-body online-panel">
      <h3>{t(locale, "onlineTitle")}</h3>
      <p className="hint">{t(locale, "onlineHint")}</p>

      <div className="field">
        <label htmlFor="teamName">{t(locale, "teamName")}</label>
        <input
          id="teamName"
          value={team}
          onChange={(event) => onTeamChange(event.target.value)}
          placeholder="default"
        />
      </div>

      <div className="row">
        <button type="button" className="secondary" disabled={!connected || busy} onClick={() => void refresh()}>
          {t(locale, "refresh")}
        </button>
        <button type="button" className="primary" disabled={!connected || busy} onClick={() => void startEvalJob()}>
          {t(locale, "runEvalHeavyJob")}
        </button>
      </div>

      <div className="field">
        <label htmlFor="shareNote">{t(locale, "shareRun")}</label>
        <input
          id="shareNote"
          value={shareNote}
          onChange={(event) => setShareNote(event.target.value)}
          placeholder={watchedRunId ?? "run_id"}
        />
        <button
          type="button"
          className="secondary compact"
          disabled={!connected || busy || !watchedRunId}
          onClick={() => void shareCurrentRun()}
        >
          {t(locale, "shareCurrentRun")}
        </button>
      </div>

      {status ? <p className="hint">{status}</p> : null}

      <strong>{t(locale, "sharedRuns")}</strong>
      <div className="list">
        {sharedRuns.length === 0 ? (
          <div className="list-item muted">{t(locale, "noSharedRuns")}</div>
        ) : (
          sharedRuns.map((item) => (
            <div key={item.share_id} className="list-item">
              <strong>{item.run_id}</strong>
              <span className="muted">
                {item.team} · {item.shared_at}
              </span>
              {item.note ? <span className="muted">{item.note}</span> : null}
            </div>
          ))
        )}
      </div>

      <strong>{t(locale, "heavyJobs")}</strong>
      <div className="list">
        {jobs.length === 0 ? (
          <div className="list-item muted">{t(locale, "noHeavyJobs")}</div>
        ) : (
          jobs.map((job) => (
            <div key={job.job_id} className="list-item">
              <strong>
                {job.job_id} · {job.job_type}
              </strong>
              <span className="muted">
                {job.state} · {job.updated_at}
              </span>
              {job.error ? <span className="hint error-text">{job.error}</span> : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
