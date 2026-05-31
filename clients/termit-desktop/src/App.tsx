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
  type ApplyPatchResponse,
  type ComposerFileContext,
  type TaskStatusResponse,
  type TaskType,
} from "@termit/client";
import { EditorPanel } from "./EditorPanel";
import { FirstRunWizard } from "./FirstRunWizard";
import {
  createEmptySession,
  deriveSessionSummary,
  deriveSessionTitle,
  loadActiveLocalId,
  loadChatSessions,
  saveActiveLocalId,
  saveChatSessions,
  upsertSession,
  type StoredChatSession,
} from "./chatSessions";
import {
  isFirstRunComplete,
  loadSettings,
  markFirstRunComplete,
  saveSettings,
  type StoredSettings,
} from "./settings";

type Tab = "chat" | "composer" | "editor" | "tasks" | "agents";

type ChatBlock =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string }
  | { id: string; kind: "meta" | "error"; text: string };

interface ContextAttachment {
  path: string;
  excerpt: string;
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
  const [apiReachable, setApiReachable] = useState(false);
  const [ollamaOk, setOllamaOk] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [statusLine, setStatusLine] = useState("Not connected");
  const [chatSessions, setChatSessions] = useState<StoredChatSession[]>(() => loadChatSessions());
  const [activeLocalId, setActiveLocalId] = useState(() => loadActiveLocalId());
  const [blocks, setBlocks] = useState<ChatBlock[]>(() => {
    const sessions = loadChatSessions();
    const activeId = loadActiveLocalId();
    const active = sessions.find((session) => session.localId === activeId) ?? sessions[0];
    return active?.blocks ?? [];
  });
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
  const [repoProfiles, setRepoProfiles] = useState<
    Array<{ profile_id: string; title: string; preferred_model: string; finetuned?: boolean }>
  >([]);
  const [attachments, setAttachments] = useState<ContextAttachment[]>([]);
  const [composerFiles, setComposerFiles] = useState<ComposerFileContext[]>([]);
  const [composerInput, setComposerInput] = useState("");
  const [composerLog, setComposerLog] = useState("Describe a multi-file change.");
  const [composerPatches, setComposerPatches] = useState<ApplyPatchRequest[]>([]);
  const [composerPatchPreviews, setComposerPatchPreviews] = useState<
    Record<string, ApplyPatchResponse>
  >({});
  const [composerBackups, setComposerBackups] = useState<Record<string, string>>({});
  const [composerBusy, setComposerBusy] = useState(false);
  const [composerPatchDetail, setComposerPatchDetail] = useState("Select a patch to preview (dry run).");
  const [showWizard, setShowWizard] = useState(() => !isFirstRunComplete());
  const [wizardHealth, setWizardHealth] = useState("");
  const [termitVersion, setTermitVersion] = useState("");
  const [missingOllamaModels, setMissingOllamaModels] = useState<string[]>([]);
  const [retrievalMode, setRetrievalMode] = useState("keyword");
  const [reindexBusy, setReindexBusy] = useState(false);

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

  useEffect(() => {
    let sessions = loadChatSessions();
    let activeId = loadActiveLocalId();
    if (sessions.length === 0) {
      const created = createEmptySession();
      sessions = [created];
      activeId = created.localId;
      saveChatSessions(sessions);
      saveActiveLocalId(activeId);
    } else if (!activeId || !sessions.some((session) => session.localId === activeId)) {
      activeId = sessions[0].localId;
      saveActiveLocalId(activeId);
    }
    setChatSessions(sessions);
    setActiveLocalId(activeId);
    const active = sessions.find((session) => session.localId === activeId);
    if (active) {
      setBlocks(active.blocks);
      if (active.sessionId !== settings.sessionId) {
        setSettings((prev) => ({ ...prev, sessionId: active.sessionId }));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bootstrap chat sessions once
  }, []);

  useEffect(() => {
    if (!activeLocalId) {
      return;
    }
    setChatSessions((prev) => {
      const updated: StoredChatSession = {
        localId: activeLocalId,
        sessionId: settings.sessionId,
        title: deriveSessionTitle(blocks),
        summary: deriveSessionSummary(blocks),
        blocks,
        updatedAt: Date.now(),
      };
      const next = upsertSession(prev, updated);
      saveChatSessions(next);
      return next;
    });
  }, [blocks, activeLocalId, settings.sessionId]);

  const updateSettings = (patch: Partial<StoredSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  };

  const pickWorkspace = async () => {
    const folder = await window.termitDesktop.pickWorkspace();
    if (folder) {
      updateSettings({ workspace: folder });
    }
  };

  const pickRepoRoot = async () => {
    const folder = await window.termitDesktop.pickRepoRoot();
    if (!folder) {
      return;
    }
    updateSettings({ repoRoot: folder });
    await window.termitDesktop.setLauncherConfig({
      repoRoot: folder,
      autoStartServer: settings.autoStartServer,
    });
  };

  const toggleAutoStartServer = async (enabled: boolean) => {
    updateSettings({ autoStartServer: enabled });
    await window.termitDesktop.setLauncherConfig({
      repoRoot: settings.repoRoot,
      autoStartServer: enabled,
    });
  };

  const startServer = async () => {
    const result = await window.termitDesktop.ensureServer(settings.baseUrl);
    setStatusLine(result.message);
    if (result.ok) {
      await connect();
    }
  };

  const connect = async () => {
    try {
      setStatusLine("Connecting...");
      const [statuses, providers, profiles, adaptersResponse, healthz, localStatus] =
        await Promise.all([
          client.providersStatus(),
          client.listProviders(),
          client.listRepoProfiles().catch(() => []),
          client.listFinetuneAdapters().catch(() => ({ adapters: [] })),
          client.healthz().catch(() => ({ status: "unknown", version: "" })),
          client.localRuntimeStatus().catch(() => ({
            providers: [],
            missing_ollama_models: [],
          })),
        ]);
      const ok = statuses.filter((item) => item.ok).length;
      const modelSet = new Set<string>(providers.flatMap((item) => item.models));
      for (const profile of profiles) {
        if (profile.preferred_model) {
          modelSet.add(profile.preferred_model);
        }
      }
      for (const adapter of adaptersResponse.adapters) {
        if (adapter.model) {
          modelSet.add(adapter.model);
        }
      }
      const modelList = [...modelSet].sort();
      setModels(modelList);
      setRepoProfiles(profiles);
      setTermitVersion(healthz.version || "");
      setMissingOllamaModels(localStatus.missing_ollama_models ?? []);
      setRetrievalMode(localStatus.retrieval_mode ?? "keyword");
      const ollama = localStatus.providers?.find((item) => item.provider === "ollama");
      setOllamaOk(Boolean(ollama?.ok));
      if (!settings.selectedModel && modelList.length > 0) {
        updateSettings({ selectedModel: modelList[0] });
      }
      if (!settings.repoProfile && profiles.length > 0) {
        updateSettings({ repoProfile: profiles[0].profile_id });
      }
      setConnected(true);
      setApiReachable(true);
      const modelLabel = settings.selectedModel || "auto";
      setStatusLine(
        `Termit v${healthz.version || "?"} · ${ok}/${statuses.length} providers · ${modelLabel}`
      );
      setWizardHealth(
        [
          `API: ${healthz.status}`,
          `version: ${healthz.version || "?"}`,
          `Ollama: ${ollama?.ok ? "ok" : ollama?.detail ?? "down"}`,
          localStatus.missing_ollama_models?.length
            ? `missing models: ${localStatus.missing_ollama_models.join(", ")}`
            : "models: ok",
        ].join("\n")
      );
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
          if (run.state === "completed" || run.state === "failed") {
            window.termitDesktop.showNotification({
              title: run.state === "completed" ? "Agent run completed" : "Agent run failed",
              body: `${run.run_id} · ${selectedAgentId ?? "agent"}`,
            });
          }
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
      const timer = window.setInterval(() => void refreshTasks(), 5000);
      return () => window.clearInterval(timer);
    }
    if (tab === "agents" && connected) {
      void refreshAgents();
    }
    return undefined;
  }, [tab, connected]);

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        await client.health();
        if (!cancelled) {
          setApiReachable(true);
        }
        if (connected) {
          const local = await client.localRuntimeStatus();
          const ollama = local.providers.find((item) => item.provider === "ollama");
          const healthz = await client.healthz().catch(() => ({ status: "unknown", version: "" }));
          if (!cancelled) {
            setOllamaOk(Boolean(ollama?.ok));
            setMissingOllamaModels(local.missing_ollama_models ?? []);
            setRetrievalMode(local.retrieval_mode ?? "keyword");
            if (healthz.version) {
              setTermitVersion(healthz.version);
            }
          }
        }
      } catch {
        if (!cancelled) {
          setApiReachable(false);
          setOllamaOk(null);
        }
      }
    };
    void probe();
    const timer = window.setInterval(() => void probe(), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [client, connected, settings.baseUrl, settings.apiKey]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const launcher = await window.termitDesktop.getLauncherConfig();
        if (cancelled) {
          return;
        }
        updateSettings({
          repoRoot: launcher.repoRoot || settings.repoRoot,
          autoStartServer: launcher.autoStartServer,
        });
        if (launcher.autoStartServer) {
          const result = await window.termitDesktop.ensureServer(settings.baseUrl);
          if (!cancelled) {
            setStatusLine(result.message);
          }
        }
        if (settings.autoConnect) {
          await connect();
        }
      } catch {
        if (!cancelled && settings.autoConnect) {
          await connect();
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on launch
  }, []);

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
        repo_profile: settings.repoProfile || undefined,
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
      setComposerPatchPreviews({});
      setComposerBackups({});
      const previews: Record<string, ApplyPatchResponse> = {};
      for (const patch of patches) {
        try {
          previews[patch.path] = await client.applyPatch({
            ...patch,
            dry_run: true,
            confirmed: false,
          });
        } catch (error) {
          const text = error instanceof Error ? error.message : String(error);
          previews[patch.path] = {
            path: patch.path,
            risk_level: "blocked",
            policy_reason: text,
            applied: false,
          };
        }
      }
      setComposerPatchPreviews(previews);
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
    const backups: Record<string, string> = { ...composerBackups };
    for (const patch of composerPatches) {
      if (backups[patch.path] !== undefined) {
        continue;
      }
      try {
        const existing = await client.readFile({ path: patch.path, max_bytes: 500_000 });
        backups[patch.path] = existing.content;
      } catch {
        backups[patch.path] = "";
      }
    }
    setComposerBackups(backups);

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

  const rollbackComposerPatches = async () => {
    if (Object.keys(composerBackups).length === 0) {
      setComposerPatchDetail("No backups — apply patches first.");
      return;
    }
    let restored = 0;
    const errors: string[] = [];
    for (const [path, content] of Object.entries(composerBackups)) {
      try {
        const result = await client.applyPatch({
          path,
          content,
          confirmed: true,
          dry_run: false,
        });
        if (result.applied) {
          restored += 1;
        } else {
          errors.push(`${path}: ${result.policy_reason ?? "skipped"}`);
        }
      } catch (error) {
        errors.push(`${path}: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
    setComposerLog((prev) => `${prev}\n\nRolled back ${restored} file(s).`);
    if (errors.length > 0) {
      setComposerPatchDetail(errors.join("\n"));
    } else {
      setComposerBackups({});
    }
  };

  const reindexCodebase = async () => {
    if (!connected || reindexBusy) {
      return;
    }
    setReindexBusy(true);
    try {
      const result = await client.reindexRetrieval();
      if (result.retrieval_mode) {
        setRetrievalMode(result.retrieval_mode);
      }
      setStatusLine(
        `Reindexed ${result.indexed_files} files · ${result.indexed_chunks} chunks · mode ${result.retrieval_mode ?? retrievalMode}`
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatusLine(text);
    } finally {
      setReindexBusy(false);
    }
  };

  const switchChatSession = (localId: string) => {
    if (localId === activeLocalId) {
      return;
    }
    const target = chatSessions.find((session) => session.localId === localId);
    if (!target) {
      return;
    }
    saveActiveLocalId(localId);
    setActiveLocalId(localId);
    setBlocks(target.blocks);
    updateSettings({ sessionId: target.sessionId });
    setDraft("");
    setAttachments([]);
  };

  const deleteChatSession = (localId: string) => {
    let next = chatSessions.filter((session) => session.localId !== localId);
    if (next.length === 0) {
      const created = createEmptySession();
      next = [created];
      saveActiveLocalId(created.localId);
      setActiveLocalId(created.localId);
      setBlocks([]);
      updateSettings({ sessionId: "" });
    } else if (localId === activeLocalId) {
      const first = next[0];
      saveActiveLocalId(first.localId);
      setActiveLocalId(first.localId);
      setBlocks(first.blocks);
      updateSettings({ sessionId: first.sessionId });
    }
    saveChatSessions(next);
    setChatSessions(next);
    setDraft("");
    setAttachments([]);
  };

  const newChatSession = () => {
    const created = createEmptySession();
    const next = upsertSession(chatSessions, created);
    saveChatSessions(next);
    saveActiveLocalId(created.localId);
    setChatSessions(next);
    setActiveLocalId(created.localId);
    setBlocks([]);
    updateSettings({ sessionId: "" });
    setDraft("");
    setAttachments([]);
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
        repo_profile: settings.repoProfile || undefined,
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
      {showWizard && (
        <FirstRunWizard
          settings={settings}
          healthLine={wizardHealth}
          busy={busy}
          onUpdate={updateSettings}
          onPickRepo={() => void pickRepoRoot()}
          onPickWorkspace={() => void pickWorkspace()}
          onConnect={() => void connect()}
          onComplete={() => {
            markFirstRunComplete();
            setShowWizard(false);
          }}
        />
      )}
      <aside className="sidebar">
        <h1>Termit</h1>
        <p>Your AI coding app — chat, composer, editor, tasks, agents via Termit + Ollama.</p>

        <div className={`status-pill ${connected ? "connected" : apiReachable ? "reachable" : ""}`}>
          {connected ? statusLine : apiReachable ? "API up — click Connect" : "API offline"}
        </div>
        <div className="health-indicators" aria-label="Service health">
          <span className={`health-dot ${apiReachable ? "ok" : "bad"}`} title="Termit API" />
          API {apiReachable ? "online" : "offline"}
          <span className={`health-dot ${ollamaOk === true ? "ok" : ollamaOk === false ? "bad" : "unknown"}`} title="Ollama" />
          Ollama {ollamaOk === true ? "ok" : ollamaOk === false ? "down" : "—"}
          {termitVersion && <span className="version-tag">v{termitVersion}</span>}
          {settings.selectedModel && (
            <span className="model-tag" title="Selected model">
              {settings.selectedModel.replace(/^ollama:/, "")}
            </span>
          )}
        </div>
        {missingOllamaModels.length > 0 && (
          <p className="hint error-text">
            Missing Ollama: {missingOllamaModels.join(", ")} — run ollama pull …
          </p>
        )}

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
          <label htmlFor="repoRoot">Termit repo (for auto-start server)</label>
          <input id="repoRoot" value={settings.repoRoot} readOnly placeholder="/path/to/Termit" />
          <button type="button" className="secondary" onClick={() => void pickRepoRoot()}>
            Choose repo
          </button>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoStartServer}
            onChange={(event) => void toggleAutoStartServer(event.target.checked)}
          />
          Start Termit server on app launch
        </label>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoConnect}
            onChange={(event) => updateSettings({ autoConnect: event.target.checked })}
          />
          Connect on launch
        </label>

        <div className="row">
          <button type="button" className="secondary" onClick={() => void startServer()}>
            Start server now
          </button>
        </div>

        <div className="field">
          <label htmlFor="workspace">Workspace folder (your code)</label>
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
        <div className="row retrieval-row">
          <span className="badge">{retrievalMode}</span>
          <button
            type="button"
            className="secondary compact"
            disabled={!connected || reindexBusy}
            onClick={() => void reindexCodebase()}
          >
            {reindexBusy ? "Reindex…" : "Reindex"}
          </button>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.inlineCompletionEnabled}
            onChange={(event) => updateSettings({ inlineCompletionEnabled: event.target.checked })}
          />
          Tab completion (Editor)
        </label>

        {repoProfiles.length > 0 && (
          <div className="field">
            <label htmlFor="repoProfile">Repo profile (routing)</label>
            <select
              id="repoProfile"
              value={settings.repoProfile}
              onChange={(event) => updateSettings({ repoProfile: event.target.value })}
            >
              <option value="">None</option>
              {repoProfiles.map((profile) => (
                <option key={profile.profile_id} value={profile.profile_id}>
                  {profile.title}
                  {profile.finetuned ? " · finetuned" : ""} → {profile.preferred_model}
                </option>
              ))}
            </select>
          </div>
        )}

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
          <button
            type="button"
            className="secondary compact"
            title="Open server logs"
            onClick={() =>
              void window.termitDesktop.openLogs().then((result) => {
                if (result.path) {
                  setStatusLine(`Log: ${result.path}`);
                }
              })
            }
          >
            Logs
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
          <div className="chat-layout">
            <aside className="chat-sessions" aria-label="Chat sessions">
              <div className="chat-sessions-header">
                <strong>Sessions</strong>
                <button type="button" className="secondary compact" onClick={newChatSession}>
                  New
                </button>
              </div>
              <div className="chat-sessions-list">
                {chatSessions.length === 0 ? (
                  <div className="chat-session-item muted">No sessions yet.</div>
                ) : (
                  chatSessions.map((session) => (
                    <div
                      key={session.localId}
                      className={`chat-session-item ${activeLocalId === session.localId ? "active" : ""}`}
                    >
                      <button
                        type="button"
                        className="chat-session-select"
                        onClick={() => switchChatSession(session.localId)}
                      >
                        <strong>{session.title}</strong>
                        {session.summary && <span className="muted">{session.summary}</span>}
                        {session.sessionId && (
                          <span className="muted session-id">{session.sessionId.slice(0, 8)}…</span>
                        )}
                      </button>
                      <button
                        type="button"
                        className="chat-session-delete"
                        aria-label={`Delete ${session.title}`}
                        onClick={() => deleteChatSession(session.localId)}
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
            </aside>
            <div className="chat-main">
            {settings.repoProfile && (
              <p className="hint repo-hint">
                Repo profile: <strong>{settings.repoProfile}</strong>
                {repoProfiles.find((p) => p.profile_id === settings.repoProfile)?.preferred_model
                  ? ` → ${repoProfiles.find((p) => p.profile_id === settings.repoProfile)?.preferred_model}`
                  : ""}
              </p>
            )}
            <div className="row chat-session-row">
              <button type="button" className="secondary compact" onClick={newChatSession}>
                New session
              </button>
              <span className="muted">session: {settings.sessionId || "auto"}</span>
            </div>
            <div className="chat-log">
              {blocks.length === 0 ? (
                <div className="message-block meta">
                  Connect (or enable auto-connect), choose workspace, attach @files, chat with
                  streaming. Models and finetune adapters load from Termit routing.
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
            </div>
          </div>
        )}

        {tab === "composer" && (
          <div className="panel-body">
            {settings.repoProfile && (
              <p className="hint repo-hint">
                Repo profile: <strong>{settings.repoProfile}</strong>
                {repoProfiles.find((p) => p.profile_id === settings.repoProfile)?.preferred_model
                  ? ` → ${repoProfiles.find((p) => p.profile_id === settings.repoProfile)?.preferred_model}`
                  : ""}
              </p>
            )}
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
                Apply all ({composerPatches.length})
              </button>
              <button
                type="button"
                className="danger"
                disabled={!connected || Object.keys(composerBackups).length === 0}
                onClick={() => void rollbackComposerPatches()}
              >
                Rollback
              </button>
            </div>
            {composerPatches.length > 0 && (
              <div className="composer-preview-list">
                <strong>Preview before apply:</strong>
                <ul>
                  {composerPatches.map((patch) => {
                    const preview = composerPatchPreviews[patch.path];
                    return (
                      <li key={patch.path}>
                        {patch.path}
                        {preview ? ` · risk ${preview.risk_level} · dry-run ok` : " · pending"}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
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
                      {composerPatchPreviews[patch.path]
                        ? `risk ${composerPatchPreviews[patch.path].risk_level}`
                        : patch.content !== undefined
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
            <div className="field">
              <label htmlFor="agentPicker">Agent profile</label>
              <select
                id="agentPicker"
                value={selectedAgentId ?? ""}
                onChange={(event) => {
                  const id = event.target.value || null;
                  setSelectedAgentId(id);
                  const agent = agents.find((item) => item.agent_id === id);
                  if (agent) {
                    setAgentDetail(
                      `${agent.name}\n${agent.description ?? ""}\nTools: ${(agent.enabled_tools ?? []).join(", ") || "none"}`
                    );
                    void refreshAgentRuns(agent.agent_id);
                  }
                }}
              >
                <option value="">Select agent…</option>
                {agents.map((agent) => (
                  <option key={agent.agent_id} value={agent.agent_id}>
                    {agent.name} ({agent.agent_id})
                  </option>
                ))}
              </select>
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
