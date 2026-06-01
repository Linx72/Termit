import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface ChangedFilesPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
  onSelectFile?: (path: string) => void;
}

interface GitChange {
  status: string;
  path: string;
}

function parseGitPorcelain(output: string): GitChange[] {
  return output
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => ({
      status: line.slice(0, 2).trim() || "?",
      path: line.slice(3).trim(),
    }))
    .filter((item) => item.path.length > 0);
}

export function ChangedFilesPanel({
  client,
  connected,
  locale,
  onSelectFile,
}: ChangedFilesPanelProps) {
  const [changes, setChanges] = useState<GitChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await client.executeCommand({
        command: "git status --porcelain",
        path: ".",
        confirmed: true,
        dry_run: false,
        timeout_seconds: 15,
      });
      if (!result.executed) {
        setError(result.policy_reason ?? "git status blocked");
        setChanges([]);
        return;
      }
      setChanges(parseGitPorcelain(result.stdout ?? ""));
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
      setChanges([]);
    } finally {
      setLoading(false);
    }
  }, [client, connected]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="changed-files" aria-label={t(locale, "changedFiles")}>
      <div className="changed-files-header">
        <strong>{t(locale, "changedFiles")}</strong>
        <button type="button" className="secondary compact" disabled={!connected || loading} onClick={() => void refresh()}>
          ↻
        </button>
      </div>
      {error && <p className="hint error-text">{error}</p>}
      <div className="changed-files-list">
        {changes.length === 0 ? (
          <div className="muted changed-files-empty">{loading ? "…" : t(locale, "noChanges")}</div>
        ) : (
          changes.map((item) => (
            <button
              key={`${item.status}-${item.path}`}
              type="button"
              className="changed-files-item"
              onClick={() => onSelectFile?.(item.path)}
              title={item.path}
            >
              <span className="git-status">{item.status}</span>
              {item.path}
            </button>
          ))
        )}
      </div>
    </div>
  );
}
