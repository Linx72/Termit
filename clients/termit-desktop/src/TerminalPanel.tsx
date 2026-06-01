import { useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface TerminalPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
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

export function TerminalPanel({ client, connected, locale }: TerminalPanelProps) {
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<TerminalEntry[]>([]);

  const runCommand = async (cmd: string) => {
    const trimmed = cmd.trim();
    if (!trimmed || !connected || busy) {
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

  const quickCommands = ["git status", "git diff --stat", "python3 -m unittest discover -s tests -q"];

  return (
    <div className="panel-body terminal-panel">
      <p className="hint">{t(locale, "terminal")} — output via Termit execute_command (RBAC).</p>
      <div className="row terminal-quick">
        {quickCommands.map((cmd) => (
          <button
            key={cmd}
            type="button"
            className="secondary compact"
            disabled={!connected || busy}
            onClick={() => void runCommand(cmd)}
          >
            {cmd}
          </button>
        ))}
      </div>
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
        <button type="button" className="primary" disabled={!connected || busy || !command.trim()} onClick={() => void runCommand(command)}>
          {t(locale, "runCommand")}
        </button>
      </div>
      <div className="terminal-history">
        {history.length === 0 ? (
          <div className="muted">No commands yet.</div>
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
