import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface TerminalPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
  workspace?: string;
  suggestedCommands?: string[];
  modeLabel?: string;
  externalBusy?: boolean;
  onCommandFinished?: (command: string) => void;
}

interface TerminalEntry {
  id: string;
  command: string;
  exitCode?: number;
  output: string;
}

function entryId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const DEFAULT_DEV_PREVIEW_URL = "http://127.0.0.1:5173";

export function TerminalPanel({
  client,
  connected,
  locale,
  workspace = "",
  suggestedCommands = [],
  modeLabel,
  externalBusy = false,
  onCommandFinished,
}: TerminalPanelProps) {
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<TerminalEntry[]>([]);
  const [webCommands, setWebCommands] = useState<string[]>([]);

  const loadWorkspaceScripts = useCallback(async () => {
    if (!connected) {
      setWebCommands([]);
      return;
    }
    try {
      const hints = await client.workspaceScripts(workspace || undefined);
      const cmds = [
        hints.dev_command,
        hints.verify_command,
        hints.scripts?.build ? "npm run build" : "",
        hints.scripts?.lint ? "npm run lint" : "",
      ].filter((item): item is string => Boolean(item?.trim()));
      setWebCommands(cmds);
    } catch {
      setWebCommands([]);
    }
  }, [client, connected, workspace]);

  useEffect(() => {
    void loadWorkspaceScripts();
  }, [loadWorkspaceScripts]);

  const runCommand = async (cmd: string) => {
    const trimmed = cmd.trim();
    if (!trimmed || !connected || busy || externalBusy) {
      return;
    }
    setBusy(true);
    try {
      const result = await client.executeCommand({
        command: trimmed,
        path: ".",
        confirmed: true,
        dry_run: false,
        timeout_seconds: 120,
      });
      const output = [
        result.policy_reason ? `policy: ${result.policy_reason}` : "",
        result.stdout?.trim() ? result.stdout.trim() : "",
        result.stderr?.trim() ? result.stderr.trim() : "",
        result.executed ? `exit ${result.exit_code ?? "?"}` : "not executed",
      ]
        .filter(Boolean)
        .join("\n");
      setHistory((prev) => [
        { id: entryId(), command: trimmed, exitCode: result.exit_code ?? undefined, output },
        ...prev,
      ].slice(0, 30));
      setCommand("");
      onCommandFinished?.(trimmed);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setHistory((prev) => [
        { id: entryId(), command: trimmed, output: text },
        ...prev,
      ].slice(0, 30));
    } finally {
      setBusy(false);
    }
  };

  const quickCommands = [
    ...webCommands,
    ...suggestedCommands,
    "git status",
    "git diff --stat",
    "python3 -m unittest discover -s tests -q",
  ].filter((item, index, all) => all.indexOf(item) === index);

  return (
    <div className="panel-body terminal-panel">
      {modeLabel ? (
        <div className="row">
          <span className="cursor-mode-badge">{modeLabel}</span>
        </div>
      ) : null}
      <p className="hint">{t(locale, "terminalHintExtended")}</p>
      <div className="row terminal-quick">
        {quickCommands.map((cmd) => (
          <button
            key={cmd}
            type="button"
            className="secondary compact"
            disabled={!connected || busy || externalBusy}
            onClick={() => void runCommand(cmd)}
          >
            {cmd}
          </button>
        ))}
      </div>
      {webCommands.some((cmd) => cmd.includes("dev")) && (
        <div className="row">
          <button
            type="button"
            className="secondary"
            onClick={() => window.open(DEFAULT_DEV_PREVIEW_URL, "_blank", "noopener,noreferrer")}
          >
            {t(locale, "devPreviewOpen")} ({DEFAULT_DEV_PREVIEW_URL})
          </button>
          <span className="muted">{t(locale, "devPreviewHint")}</span>
        </div>
      )}
      <div className="row">
        <input
          className="terminal-input"
          value={command}
          placeholder={t(locale, "commandPlaceholder")}
          onChange={(event) => setCommand(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void runCommand(command);
            }
          }}
        />
        <button type="button" className="primary" disabled={!connected || busy || externalBusy || !command.trim()} onClick={() => void runCommand(command)}>
          {t(locale, "runCommand")}
        </button>
      </div>
      <div className="terminal-history">
        {history.length === 0 ? (
          <div className="muted">{t(locale, "terminalNoCommands")}</div>
        ) : (
          history.map((entry) => (
            <pre key={entry.id} className="detail-box terminal-entry">
              <strong>$ {entry.command}</strong>
              {"\n"}
              {entry.output}
            </pre>
          ))
        )}
      </div>
    </div>
  );
}
