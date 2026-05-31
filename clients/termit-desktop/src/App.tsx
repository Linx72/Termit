import { useEffect, useMemo, useState } from "react";
import {
  TermitClient,
  buildComposerMessage,
  parseComposerPatches,
  stripComposerJsonBlock,
  formatAgentTimeline,
  watchAgentRun,
  type AgentProfile,
  type AgentRunRecord,
  type ApplyPatchRequest,
  type ComposerFileContext,
  type TaskStatusResponse,
  type TaskType,
} from "@termit/client";
import { EditorPanel } from "./EditorPanel";

type Tab = "chat" | "composer" | "editor" | "tasks" | "agents";

type ChatBlock =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string }
  | { id: string; kind: "meta" | "error"; text: string };

const STORAGE_KEY = "termit-app-settings";

interface StoredSettings {
  baseUrl: string;
  apiKey: string;
  sessionId: string;
  workspace: string;
  taskType: TaskType;
  useRetrieval: boolean;
  selectedModel: string;
  inlineCompletionEnabled: boolean;
}

interface ContextAttachment {
  path: string;
  excerpt: string;
}

function loadSettings(): StoredSettings {
  const defaults: StoredSettings = {
    baseUrl: "http://127.0.0.1:8765",
    apiKey: "",
    sessionId: "",
    workspace: "",
    taskType: "coding",
    useRetrieval: false,
    selectedModel: "",
    inlineCompletionEnabled: false,
  };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return defaults;
    }
    return { ...defaults, ...JSON.parse(raw) };
  } catch {
    return defaults;
  }
}

function saveSettings(settings: StoredSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

function blockId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function workspacePrefix(workspace: string): string {
  if (!workspace) {
    return "";
  }
  const parts = workspace.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] ?? "";
}

function buildMessageWithAttachments(message: string, attachments: ContextAttachment[]): string {
  if (attachments.length === 0) {
    return message;
  }
  const blocks = attachments.map(
    (item) => `@file ${item.path}\n\`\`\`\n${item.excerpt}\n\`\`\``
  );
  return `${message.trim()}\n\n---\n${blocks.join("\n\n")}`;
}

export function App() {
  const [settings, setSettings] = useState<StoredSettings>(() => loadSettings());
  const [tab, setTab] = useState<Tab>("chat");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [statusLine, setStatusLine] = useState("Not connected");
  const [blocks, setBlocks] = useState<ChatBlock[]>([]);
  const [draft, setDraft] = useState("");
  const [tasks, setTasks] = useState<TaskStatusResponse[]>([]);
  const [taskDetail, setTaskDetail] = useState("Select a task.");
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentInput, setAgentInput] = useState("");
  const [agentDetail, setAgentDetail] = useState("Select an agent.");
  const [agentRuns, setAgentRuns] = useState<AgentRunRecord[]>([]);
  const [watchedRunId, setWatchedRunId] = useState<string | null>(null);
  const [agentTimeline, setAgentTimeline] = useState("Run timeline appears here.");
  const [models, setModels] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<ContextAttachment[]>([]);
  const [composerFiles, setComposerFiles] = useState<ComposerFileContext[]>([]);
  const [composerInput, setComposerInput] = useState("");
  const [composerLog, setComposerLog] = useState("Describe a multi-file change.");
  const [composerPatches, setComposerPatches] = useState<ApplyPatchRequest[]>([]);
  const [composerBusy, setComposerBusy] = useState(false);
  const [composerPatchDetail, setComposerPatchDetail] = useState("Select a patch to preview (dry run).");

  const client = useMemo(
    () =>
      new TermitClient({
        baseUrl: settings.baseUrl,
        apiKey: settings.apiKey || undefined,
      }),
    [settings.baseUrl, settings.apiKey]
  );

  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  const updateSettings = (patch: Partial<StoredSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  };

  const pickWorkspace = async () => {
    const folder = await window.termitDesktop.pickWorkspace();
    if (folder) {
      updateSettings({ workspace: folder });
    }
  };

  const connect = async () => {
    try {
      setStatusLine("Connecting...");
      const [statuses, providers] = await Promise.all([
        client.providersStatus(),
        client.listProviders(),
      ]);
      const ok = statuses.filter((item) => item.ok).length;
      const modelList = providers.flatMap((item) => item.models);
      setModels(modelList);
      if (!settings.selectedModel && modelList.length > 0) {
        updateSettings({ selectedModel: modelList[0] });
      }
      setConnected(true);
      setStatusLine(`Termit · ${ok}/${statuses.length} providers OK`);
      setBlocks((prev) => [
        ...prev,
        { id: blockId(), kind: "meta", text: `Connected to ${settings.baseUrl}` },
      ]);
    } catch (error) {
      setConnected(false);
      const message = error instanceof Error ? error.message : String(error);
      setStatusLine(message);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text: message }]);
    }
  };

  const refreshTasks = async () => {
    const response = await client.listTasks(30);
    setTasks(response.tasks);
  };

  const refreshAgents = async () => {
    const list = await client.listAgents();
    setAgents(list);
  };

  const refreshAgentRuns = async (agentId: string) => {
    const response = await client.listAgentRuns(agentId, 15);
    setAgentRuns(response.runs);
  };

  useEffect(() => {
    if (!watchedRunId || !connected) {
      return;
    }
    const abort = new AbortController();
    void watchAgentRun(
      client,
      watchedRunId,
      ({ run, events }) => {
        setAgentTimeline(formatAgentTimeline(run, events));
        if (["completed", "failed", "cancelled"].includes(run.state)) {
          setWatchedRunId(null);
        }
      },
      { signal: abort.signal, pollMs: 500, timeoutSeconds: 600 }
    ).catch((error) => {
      if (abort.signal.aborted) {
        return;
      }
      const text = error instanceof Error ? error.message : String(error);
      setAgentTimeline(text);
      setWatchedRunId(null);
    });
    return () => {
      abort.abort();
    };
  }, [watchedRunId, connected, client]);

  useEffect(() => {
    if (tab === "tasks" && connected) {
      void refreshTasks();
    }
    if (tab === "agents" && connected) {
      void refreshAgents();
    }
  }, [tab, connected]);

  const attachFile = async () => {
    if (!settings.workspace) {
      setBlocks((prev) => [
        ...prev,
        { id: blockId(), kind: "error", text: "Choose a workspace folder first." },
      ]);
      return;
    }
    const relativePath = await window.termitDesktop.pickWorkspaceFile(settings.workspace);
    if (!relativePath) {
      return;
    }
    try {
      const file = await client.readFile({ path: relativePath, max_bytes: 12000 });
      setAttachments((prev) => [
        ...prev.filter((item) => item.path !== relativePath),
        { path: relativePath, excerpt: file.content },
      ]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    }
  };

  const attachComposerFile = async () => {
    if (!settings.workspace) {
      return;
    }
    const relativePath = await window.termitDesktop.pickWorkspaceFile(settings.workspace);
    if (!relativePath) {
      return;
    }
    try {
      const file = await client.readFile({ path: relativePath, max_bytes: 12000 });
      setComposerFiles((prev) => [
        ...prev.filter((item) => item.path !== relativePath),
        { path: relativePath, content: file.content },
      ]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setComposerLog(text);
    }
  };

  const runComposer = async () => {
    const instruction = composerInput.trim();
    if (!instruction || !connected || composerBusy) {
      return;
    }
    setComposerBusy(true);
    setComposerLog("Running Composer...\n");
    setComposerPatches([]);
    let responseText = "";
    try {
      for await (const event of client.chatStream({
        message: buildComposerMessage(instruction, composerFiles),
        task_type: "coding",
        session_id: settings.sessionId || undefined,
        model: settings.selectedModel || undefined,
        use_retrieval: true,
        retrieval_path_prefix: workspacePrefix(settings.workspace),
      })) {
        if (event.event === "meta") {
          const nextSession = String(event.data.session_id ?? "");
          if (nextSession) {
            updateSettings({ sessionId: nextSession });
          }
        } else if (event.event === "token") {
          responseText += String(event.data.text ?? "");
          setComposerLog((prev) => prev + String(event.data.text ?? ""));
        }
      }
      const patches = parseComposerPatches(responseText);
      setComposerPatches(patches);
      const prose = stripComposerJsonBlock(responseText);
      setComposerLog(
        `${prose}\n\n---\nParsed ${patches.length} patch(es). Click a file to dry-run preview.`
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setComposerLog(text);
    } finally {
      setComposerBusy(false);
    }
  };

  const previewComposerPatch = async (patch: ApplyPatchRequest) => {
    try {
      const preview = await client.applyPatch({ ...patch, dry_run: true, confirmed: false });
      setComposerPatchDetail(
        [
          `path: ${patch.path}`,
          `risk: ${preview.risk_level}`,
          preview.policy_reason ? `policy: ${preview.policy_reason}` : "",
          preview.preview_excerpt ? `preview:\n${preview.preview_excerpt}` : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setComposerPatchDetail(text);
    }
  };

  const applyAllComposerPatches = async () => {
    if (composerPatches.length === 0) {
      return;
    }
    let applied = 0;
    const errors: string[] = [];
    for (const patch of composerPatches) {
      try {
        const result = await client.applyPatch({ ...patch, confirmed: true, dry_run: false });
        if (result.applied) {
          applied += 1;
        } else {
          errors.push(`${patch.path}: ${result.policy_reason ?? "skipped"}`);
        }
      } catch (error) {
        errors.push(`${patch.path}: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
    setComposerLog((prev) => `${prev}\n\nApplied ${applied}/${composerPatches.length} patches.`);
    if (errors.length > 0) {
      setComposerPatchDetail(errors.join("\n"));
    }
  };

  const sendChat = async () => {
    const message = draft.trim();
    if (!message || !connected || busy) {
      return;
    }
    const fullMessage = buildMessageWithAttachments(message, attachments);
    setDraft("");
    setAttachments([]);
    setBusy(true);
    setBlocks((prev) => [
      ...prev,
      { id: blockId(), kind: "user", text: fullMessage },
      { id: blockId(), kind: "assistant", text: "" },
    ]);

    let sessionId = settings.sessionId || undefined;
    const prefix = workspacePrefix(settings.workspace);
    try {
      for await (const event of client.chatStream({
        message: fullMessage,
        task_type: settings.taskType,
        session_id: sessionId,
        model: settings.selectedModel || undefined,
        use_retrieval: settings.useRetrieval,
        retrieval_path_prefix: prefix,
      })) {
        if (event.event === "meta") {
          const nextSession = String(event.data.session_id ?? "");
          if (nextSession && nextSession !== settings.sessionId) {
            sessionId = nextSession;
            updateSettings({ sessionId: nextSession });
          }
          setBlocks((prev) => [
            ...prev,
            {
              id: blockId(),
              kind: "meta",
              text: `model: ${String(event.data.model)} · retrieval hits: ${String(event.data.retrieval_hits ?? 0)}`,
            },
          ]);
        } else if (event.event === "token") {
          const token = String(event.data.text ?? "");
          setBlocks((prev) => {
            const last = prev[prev.length - 1];
            if (last?.kind === "assistant") {
              return [...prev.slice(0, -1), { ...last, text: last.text + token }];
            }
            return [...prev, { id: blockId(), kind: "assistant", text: token }];
          });
        } else if (event.event === "error") {
          setBlocks((prev) => [
            ...prev,
            { id: blockId(), kind: "error", text: JSON.stringify(event.data) },
          ]);
        }
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    } finally {
      setBusy(false);
    }
  };

  const queueTask = async () => {
    const input = draft.trim();
    if (!input) {
      return;
    }
    const task = await client.createTask({
      input,
      task_type: settings.taskType,
      session_id: settings.sessionId || undefined,
    });
    setBlocks((prev) => [
      ...prev,
      { id: blockId(), kind: "meta", text: `Task queued: ${task.task_id} (${task.state})` },
    ]);
    setDraft("");
    void refreshTasks();
  };

  const runAgent = async () => {
    if (!selectedAgentId || !agentInput.trim()) {
      return;
    }
    const run = await client.createAgentRun(selectedAgentId, {
      input: agentInput.trim(),
      session_id: settings.sessionId || undefined,
    });
    setAgentDetail(`Run queued: ${run.run_id} (${run.state})`);
    setAgentInput("");
    setWatchedRunId(run.run_id);
    void refreshAgentRuns(selectedAgentId);
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Termit</h1>
        <p>Cursor-like workflow: chat, @files, tasks, agents — powered by your Termit models.</p>

        <div className={`status-pill ${connected ? "connected" : ""}`}>
          {connected ? statusLine : "Offline"}
        </div>

        <div className="field">
          <label htmlFor="baseUrl">Termit API URL</label>
          <input
            id="baseUrl"
            value={settings.baseUrl}
            onChange={(event) => updateSettings({ baseUrl: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="apiKey">X-API-Key (optional)</label>
          <input
            id="apiKey"
            type="password"
            value={settings.apiKey}
            placeholder="dev-key if auth enabled"
            onChange={(event) => updateSettings({ apiKey: event.target.value })}
          />
          <span className="hint">Only if TERMIT_AUTH_ENABLED=true in server .env</span>
        </div>

        <div className="field">
          <label htmlFor="workspace">Workspace folder</label>
          <input id="workspace" value={settings.workspace} readOnly />
          <button type="button" className="secondary" onClick={() => void pickWorkspace()}>
            Choose folder
          </button>
        </div>

        <div className="field">
          <label htmlFor="taskType">Default task type</label>
          <select
            id="taskType"
            value={settings.taskType}
            onChange={(event) =>
              updateSettings({ taskType: event.target.value as TaskType })
            }
          >
            <option value="coding">coding</option>
            <option value="review">review</option>
            <option value="debug">debug</option>
            <option value="explain">explain</option>
            <option value="general">general</option>
          </select>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.useRetrieval}
            onChange={(event) => updateSettings({ useRetrieval: event.target.checked })}
          />
          @codebase retrieval
        </label>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.inlineCompletionEnabled}
            onChange={(event) => updateSettings({ inlineCompletionEnabled: event.target.checked })}
          />
          Tab completion (Editor)
        </label>

        <div className="field">
          <label htmlFor="model">Model</label>
          <select
            id="model"
            value={settings.selectedModel}
            onChange={(event) => updateSettings({ selectedModel: event.target.value })}
          >
            <option value="">Auto (router)</option>
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>

        <div className="row">
          <button type="button" className="primary" onClick={() => void connect()}>
            {connected ? "Refresh connection" : "Connect"}
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="tabs">
          {(["chat", "composer", "editor", "tasks", "agents"] as Tab[]).map((name) => (
            <button
              key={name}
              type="button"
              className={`tab ${tab === name ? "active" : ""}`}
              onClick={() => setTab(name)}
            >
              {name.charAt(0).toUpperCase() + name.slice(1)}
            </button>
          ))}
        </div>

        {tab === "chat" && (
          <>
            <div className="chat-log">
              {blocks.length === 0 ? (
                <div className="message-block meta">
                  Cursor-style UX, Termit backend: Connect, attach @files, pick a model, chat with
                  streaming. Models from Ollama via Termit — no Cursor subscription.
                </div>
              ) : (
                blocks.map((block) => (
                  <div key={block.id} className={`message-block ${block.kind}`}>
                    {block.kind === "user" && <strong>You</strong>}
                    {block.kind === "assistant" && <strong>Termit</strong>}
                    {block.kind === "error" && <strong>Error</strong>}
                    {block.kind === "meta" && <strong>Info</strong>}
                    {"\n"}
                    {block.text}
                  </div>
                ))
              )}
            </div>
            <div className="composer">
              {attachments.length > 0 && (
                <div className="chips">
                  {attachments.map((item) => (
                    <span key={item.path} className="chip">
                      @{item.path}
                      <button
                        type="button"
                        aria-label={`Remove ${item.path}`}
                        onClick={() =>
                          setAttachments((prev) => prev.filter((a) => a.path !== item.path))
                        }
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <textarea
                value={draft}
                placeholder="Ask Termit to implement, review, or debug..."
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault();
                    void sendChat();
                  }
                }}
              />
              <div className="composer-actions">
                <button
                  type="button"
                  className="primary"
                  disabled={!connected || busy}
                  onClick={() => void sendChat()}
                >
                  Send
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={!connected}
                  onClick={() => void attachFile()}
                >
                  @ file
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={!connected || !draft.trim()}
                  onClick={() => void queueTask()}
                >
                  Queue task
                </button>
              </div>
              <p className="hint">Cmd/Ctrl+Enter to send · session: {settings.sessionId || "auto"}</p>
            </div>
          </>
        )}

        {tab === "composer" && (
          <div className="panel-body">
            <p className="hint">
              Composer: attach several @files, describe a multi-file change, review patches, apply all.
            </p>
            <div className="chips">
              {composerFiles.map((file) => (
                <span key={file.path} className="chip">
                  @{file.path}
                  <button
                    type="button"
                    onClick={() =>
                      setComposerFiles((prev) => prev.filter((item) => item.path !== file.path))
                    }
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="row">
              <button type="button" className="secondary" disabled={!connected} onClick={() => void attachComposerFile()}>
                @ add file
              </button>
              <button type="button" className="secondary" onClick={() => setComposerFiles([])}>
                Clear files
              </button>
            </div>
            <textarea
              value={composerInput}
              placeholder="Refactor auth across api/ and tests/..."
              onChange={(event) => setComposerInput(event.target.value)}
            />
            <div className="row">
              <button
                type="button"
                className="primary"
                disabled={!connected || composerBusy || !composerInput.trim()}
                onClick={() => void runComposer()}
              >
                Run Composer
              </button>
              <button
                type="button"
                className="secondary"
                disabled={!connected || composerPatches.length === 0}
                onClick={() => void applyAllComposerPatches()}
              >
                Apply all
              </button>
            </div>
            <pre className="detail-box composer-log">{composerLog}</pre>
            <div className="list">
              {composerPatches.length === 0 ? (
                <div className="list-item muted">Patches appear after Composer run.</div>
              ) : (
                composerPatches.map((patch) => (
                  <button
                    key={patch.path}
                    type="button"
                    className="list-item"
                    onClick={() => void previewComposerPatch(patch)}
                  >
                    <strong>{patch.path}</strong>
                    <span className="muted">
                      {patch.content !== undefined
                        ? "full file"
                        : `${patch.hunks?.length ?? 0} hunk(s)`}
                    </span>
                  </button>
                ))
              )}
            </div>
            <pre className="detail-box">{composerPatchDetail}</pre>
          </div>
        )}

        {tab === "editor" && (
          <EditorPanel
            client={client}
            connected={connected}
            workspace={settings.workspace}
            selectedModel={settings.selectedModel}
            sessionId={settings.sessionId}
            inlineCompletionEnabled={settings.inlineCompletionEnabled}
            onSessionId={(id) => updateSettings({ sessionId: id })}
          />
        )}

        {tab === "tasks" && (
          <div className="panel-body">
            <div className="row">
              <button type="button" className="secondary" disabled={!connected} onClick={() => void refreshTasks()}>
                Refresh
              </button>
            </div>
            <div className="list">
              {tasks.length === 0 ? (
                <div className="list-item muted">No tasks yet.</div>
              ) : (
                tasks.map((task) => (
                  <button
                    key={task.task_id}
                    type="button"
                    className="list-item"
                    onClick={async () => {
                      const detail = await client.getTask(task.task_id);
                      setTaskDetail(
                        [
                          `task_id: ${detail.task_id}`,
                          `state: ${detail.state}`,
                          `type: ${detail.task_type}`,
                          detail.error ? `error: ${detail.error}` : "",
                          detail.report ? `report:\n${detail.report}` : "",
                        ]
                          .filter(Boolean)
                          .join("\n")
                      );
                    }}
                  >
                    <strong>{task.task_id}</strong>
                    <span className="muted">
                      {task.state} · {task.task_type}
                    </span>
                  </button>
                ))
              )}
            </div>
            <pre className="detail-box">{taskDetail}</pre>
          </div>
        )}

        {tab === "agents" && (
          <div className="panel-body">
            <div className="row">
              <button type="button" className="secondary" disabled={!connected} onClick={() => void refreshAgents()}>
                Refresh agents
              </button>
            </div>
            <div className="list">
              {agents.length === 0 ? (
                <div className="list-item muted">No agents configured on server.</div>
              ) : (
                agents.map((agent) => (
                  <button
                    key={agent.agent_id}
                    type="button"
                    className={`list-item ${selectedAgentId === agent.agent_id ? "selected" : ""}`}
                    onClick={() => {
                      setSelectedAgentId(agent.agent_id);
                      setAgentDetail(
                        `${agent.name}\n${agent.description ?? ""}\nTools: ${(agent.enabled_tools ?? []).join(", ") || "none"}`
                      );
                      void refreshAgentRuns(agent.agent_id);
                    }}
                  >
                    <strong>{agent.name}</strong>
                    <span className="muted">
                      {agent.agent_id} · {agent.task_type}
                    </span>
                  </button>
                ))
              )}
            </div>
            <div className="list">
              {agentRuns.length === 0 ? (
                <div className="list-item muted">Select an agent to list recent runs.</div>
              ) : (
                agentRuns.map((run) => (
                  <button
                    key={run.run_id}
                    type="button"
                    className={`list-item ${watchedRunId === run.run_id ? "selected" : ""}`}
                    onClick={() => setWatchedRunId(run.run_id)}
                  >
                    <strong>{run.run_id}</strong>
                    <span className="muted">
                      {run.state} · {run.updated_at}
                    </span>
                  </button>
                ))
              )}
            </div>
            <textarea
              value={agentInput}
              placeholder="Prompt for selected agent..."
              onChange={(event) => setAgentInput(event.target.value)}
            />
            <div className="row">
              <button
                type="button"
                className="primary"
                disabled={!connected || !selectedAgentId || !agentInput.trim()}
                onClick={() => void runAgent()}
              >
                Run agent
              </button>
            </div>
            <pre className="detail-box">{agentDetail}</pre>
            <pre className="detail-box">{agentTimeline}</pre>
          </div>
        )}
      </main>
    </div>
  );
}
