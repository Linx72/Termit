import { useEffect, useMemo, useRef, useState } from "react";
import {
  TermitClient,
  buildComposerMessage,
  buildComponentComposerMessage,
  filterComposerPatchesToPaths,
  parseComposerPatches,
  stripComposerJsonBlock,
  formatAgentTimeline,
  watchAgentRun,
  type AgentProfile,
  type AgentRunRecord,
  type AgentRunEvent,
  type ApplyPatchRequest,
  type ApplyPatchResponse,
  type ComposerFileContext,
  type TaskStatusResponse,
  type TaskType,
  listDesktopJourneys,
  listPolicyPresets,
  type AgentPolicyPreset,
  type DesktopJourney,
} from "@termit/client";
import { FirstRunWizard } from "./FirstRunWizard";
import {
  attachmentPaths,
  buildMessageWithAttachments,
  excerptAroundLine,
  type ContextAttachment,
} from "./contextAttachments";
import { t, stepLabel } from "./i18n";
import {
  createEmptySession,
  deriveSessionSummary,
  deriveSessionTitle,
  loadActiveLocalId,
  loadChatSessions,
  renameSession,
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
import { PolicyPresetSelector } from "./PolicyPresetSelector";
import { MediaStudioPanel } from "./MediaStudioPanel";
import {
  dryRunAllPatches,
  formatSafeApplyHint,
  summarizePatchRisk,
  type SafeApplySummary,
} from "./composerSafeApply";
import { suggestContextFiles, type ContextSuggestion } from "./contextSuggestions";
import { journeyDescription, journeyTitle, parseCheckpointSummary } from "./northStar";
import { trackWorkflowEvent } from "./workflowTelemetry";
import {
  buildPresetDraft,
  CROSS_PLATFORM_PRESETS,
  launchCrossPlatformPreset,
} from "./crossPlatformPresets";
import { buildCompletionSuggestions, formatActivityTape } from "./activityTape";
import { executionModeLabel, isBuildTask } from "./buildTask";


type AgentFolder = {
  id: string;
  label: string;
  sessions: StoredChatSession[];
};

type GitChange = {
  status: string;
  path: string;
};

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

type ChatBlock =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string }
  | { id: string; kind: "tape"; text: string }
  | { id: string; kind: "suggestions"; text: string; actions?: string[] }
  | { id: string; kind: "meta" | "error"; text: string };

const DEFAULT_AGENT_TEMPLATE = "web-app-vite";

function blockId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parseGitShortstat(output: string): { added: number; deleted: number } {
  const insertMatch = output.match(/(\d+)\s+insertion/i);
  const deleteMatch = output.match(/(\d+)\s+deletion/i);
  return {
    added: insertMatch ? Number(insertMatch[1]) : 0,
    deleted: deleteMatch ? Number(deleteMatch[1]) : 0,
  };
}

function workspacePrefix(workspace: string): string {
  if (!workspace) {
    return "";
  }
  const parts = workspace.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] ?? "";
}

function formatAgentProfileDetail(agent: AgentProfile): string {
  return [
    agent.name,
    agent.description ?? "",
    `Max tool steps: ${agent.max_tool_steps ?? 6}`,
    `Tool loop: ${agent.use_tool_loop ? "on" : "off"}`,
    `Tools: ${(agent.enabled_tools ?? []).join(", ") || "none"}`,
  ]
    .filter(Boolean)
    .join("\n");
}

function countToolSteps(events: Array<{ event_type: string }>): number {
  return events.filter((event) => event.event_type.toLowerCase().includes("tool")).length;
}

export function App() {
  const [settings, setSettings] = useState<StoredSettings>(() => loadSettings());
  const [connected, setConnected] = useState(false);
  const [apiReachable, setApiReachable] = useState(false);
  const [ollamaOk, setOllamaOk] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [atomicBusy, setAtomicBusy] = useState(false);
  const [atomicProgress, setAtomicProgress] = useState("");
  const [statusLine, setStatusLine] = useState("Not connected");
  const [chatSessions, setChatSessions] = useState<StoredChatSession[]>(() => loadChatSessions());
  const [activeLocalId, setActiveLocalId] = useState(() => loadActiveLocalId());
  const [blocks, setBlocks] = useState<ChatBlock[]>(() => {
    const sessions = loadChatSessions();
    const activeId = loadActiveLocalId();
    const active = sessions.find((session) => session.localId === activeId) ?? sessions[0];
    return active?.blocks ?? [];
  });
  const chatLogRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState("");
  const [tasks, setTasks] = useState<TaskStatusResponse[]>([]);
  const [taskDetail, setTaskDetail] = useState("Select a task.");
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentInput, setAgentInput] = useState("");
  const [agentDetail, setAgentDetail] = useState("Select an agent.");
  const [agentRuns, setAgentRuns] = useState<AgentRunRecord[]>([]);
  const [watchedRunId, setWatchedRunId] = useState<string | null>(null);
  const [awaitingConfirmationRunId, setAwaitingConfirmationRunId] = useState<string | null>(null);
  const [watchedRunState, setWatchedRunState] = useState<string | null>(null);
  const [toolStepCount, setToolStepCount] = useState(0);
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
  const [composerMode, setComposerMode] = useState<"multi" | "component">("multi");
  const [composerPatchDetail, setComposerPatchDetail] = useState("Select a patch to preview (dry run).");
  const [showWizard, setShowWizard] = useState(() => !isFirstRunComplete());
  const [wizardHealth, setWizardHealth] = useState("");
  const [termitVersion, setTermitVersion] = useState("");
  const [missingOllamaModels, setMissingOllamaModels] = useState<string[]>([]);
  const [retrievalMode, setRetrievalMode] = useState("semantic");
  const [reindexBusy, setReindexBusy] = useState(false);
  const [projectRulesText, setProjectRulesText] = useState("");
  const [userRulesText, setUserRulesText] = useState("");
  const [selectedProjectSkills, setSelectedProjectSkills] = useState<string[]>([]);
  const [rulesSaving, setRulesSaving] = useState(false);
  const [sessionSearch, setSessionSearch] = useState("");
  const [folderDraft, setFolderDraft] = useState("");
  const [selectedFolder, setSelectedFolder] = useState<string>("General");
  const [liveChanges, setLiveChanges] = useState<GitChange[]>([]);
  const [liveChangesLoading, setLiveChangesLoading] = useState(false);
  const [liveChangesError, setLiveChangesError] = useState("");
  const [selectedChangePath, setSelectedChangePath] = useState("");
  const [selectedChangePreview, setSelectedChangePreview] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reviewStats, setReviewStats] = useState({ added: 0, deleted: 0 });
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [pullingModel, setPullingModel] = useState<string | null>(null);
  const [editorOpenPath, setEditorOpenPath] = useState<string | null>(null);
  const [northStarJourneys, setNorthStarJourneys] = useState<DesktopJourney[]>([]);
  const [policyPresets, setPolicyPresets] = useState<AgentPolicyPreset[]>([]);
  const [safeApplySummary, setSafeApplySummary] = useState<SafeApplySummary | null>(null);
  const [contextSuggestions, setContextSuggestions] = useState<ContextSuggestion[]>([]);
  const [pendingVerifyCommands, setPendingVerifyCommands] = useState<string[]>([]);
  const [checkpointLine, setCheckpointLine] = useState("");

  const locale = settings.locale;
  const [platformSkills, setPlatformSkills] = useState<Array<{ skill_id: string; name: string }>>([]);
  const [platformSchedules, setPlatformSchedules] = useState<
    Array<{ schedule_id: string; agent_id: string; cron: string; enabled: boolean }>
  >([]);
  const [platformMcpServers, setPlatformMcpServers] = useState<
    Array<{ server_id: string; name: string; command: string; enabled: boolean }>
  >([]);
  const [mcpDraftName, setMcpDraftName] = useState("");
  const [mcpDraftCommand, setMcpDraftCommand] = useState("");
  const [mcpDraftArgs, setMcpDraftArgs] = useState("");
  const [mcpSaving, setMcpSaving] = useState(false);
  const [mcpImportBusy, setMcpImportBusy] = useState(false);
  const [runSpansText, setRunSpansText] = useState("Select a run to view trace spans.");
  const [platformStatus, setPlatformStatus] = useState("Platform services not loaded.");

  const projectId = useMemo(() => workspacePrefix(settings.workspace), [settings.workspace]);
  const activeAgentLabel = useMemo(() => {
    const agent = agents.find((item) => item.agent_id === selectedAgentId);
    return agent?.name || "General";
  }, [agents, selectedAgentId]);
  const chatFolders = useMemo<AgentFolder[]>(() => {
    const map = new Map<string, StoredChatSession[]>();
    for (const session of chatSessions) {
      const label = (session.agentFolder || "General").trim() || "General";
      if (!map.has(label)) {
        map.set(label, []);
      }
      map.get(label)!.push(session);
    }
    return [...map.entries()].map(([label, sessions]) => ({
      id: label.toLowerCase().replace(/\s+/g, "-"),
      label,
      sessions: sessions.sort((a, b) => b.updatedAt - a.updatedAt),
    }));
  }, [chatSessions]);

  const client = useMemo(
    () =>
      new TermitClient({
        baseUrl: settings.baseUrl,
        apiKey: settings.apiKey || undefined,
        workspace: settings.workspace || undefined,
      }),
    [settings.baseUrl, settings.apiKey, settings.workspace]
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
        agentFolder:
          prev.find((item) => item.localId === activeLocalId)?.agentFolder || activeAgentLabel,
        blocks,
        updatedAt: Date.now(),
      };
      const next = upsertSession(prev, updated);
      saveChatSessions(next);
      return next;
    });
  }, [blocks, activeLocalId, settings.sessionId]);

  useEffect(() => {
    const el = chatLogRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [blocks]);

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

  const syncLauncherConfig = async (patch?: Partial<Pick<StoredSettings, "repoRoot" | "autoStartServer">>) => {
    const repoRoot = patch?.repoRoot ?? settings.repoRoot;
    const autoStartServer = patch?.autoStartServer ?? settings.autoStartServer;
    await window.termitDesktop.setLauncherConfig({ repoRoot, autoStartServer });
  };

  const startServer = async (): Promise<boolean> => {
    const result = await window.termitDesktop.ensureServer(settings.baseUrl);
    setStatusLine(result.message);
    if (result.ok) {
      setApiReachable(true);
      return connect();
    }
    return false;
  };

  const connect = async (): Promise<boolean> => {
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
      void refreshAgents();
      void refreshPlatformData(selectedAgentId);
      void refreshLiveChanges();
      void listDesktopJourneys(client)
        .then((response) => setNorthStarJourneys(response.journeys))
        .catch(() => setNorthStarJourneys([]));
      void listPolicyPresets(client)
        .then((items) => setPolicyPresets(items))
        .catch(() => setPolicyPresets([]));
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
      if (projectId) {
        try {
          const rules = await client.getProjectRules(projectId);
          setProjectRulesText(rules.project_rules ?? "");
          setUserRulesText(rules.user_rules ?? "");
          setSelectedProjectSkills(Array.isArray(rules.skills) ? rules.skills : []);
        } catch {
          setProjectRulesText("");
          setUserRulesText("");
        }
      }
      return true;
    } catch (error) {
      setConnected(false);
      const message = error instanceof Error ? error.message : String(error);
      setStatusLine(message);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text: message }]);
      return false;
    }
  };

  const ensureApiReady = async (): Promise<boolean> => {
    if (connected) {
      return true;
    }
    try {
      await client.health();
      setApiReachable(true);
      const ok = await connect();
      if (ok) {
        return true;
      }
    } catch {
      setApiReachable(false);
    }
    if (settings.repoRoot.trim()) {
      setStatusLine(locale === "ru" ? "Запуск Termit API…" : "Starting Termit API…");
      return startServer();
    }
    return false;
  };

  const refreshTasks = async () => {
    const response = await client.listTasks(30);
    setTasks(response.tasks);
  };

  const refreshAgents = async () => {
    const list = await client.listAgents();
    setAgents(list);
    if (list.length > 0) {
      setSelectedAgentId((prev) => prev ?? list[0].agent_id);
    }
  };

  const resolveAgentIdForRun = async (
    preferredId?: string | null,
    taskInput?: string
  ): Promise<string | null> => {
    if (preferredId?.trim()) {
      return preferredId.trim();
    }
    if (selectedAgentId?.trim()) {
      return selectedAgentId.trim();
    }
    const templateId =
      taskInput && isBuildTask(taskInput) ? "web-app-vite" : DEFAULT_AGENT_TEMPLATE;
    if (agents.length > 0 && templateId === DEFAULT_AGENT_TEMPLATE) {
      return agents[0].agent_id;
    }
    try {
      const list = await client.listAgents();
      setAgents(list);
      const matched = list.find((item) => item.name.toLowerCase().includes("web app"));
      if (matched && isBuildTask(taskInput ?? "")) {
        setSelectedAgentId(matched.agent_id);
        return matched.agent_id;
      }
      if (list.length > 0 && templateId === DEFAULT_AGENT_TEMPLATE) {
        const id = list[0].agent_id;
        setSelectedAgentId(id);
        return id;
      }
      const profile = await client.ensureAgentFromTemplate(templateId);
      setAgents((prev) => {
        if (prev.some((item) => item.agent_id === profile.agent_id)) {
          return prev;
        }
        return [...prev, profile];
      });
      setSelectedAgentId(profile.agent_id);
      return profile.agent_id;
    } catch {
      return null;
    }
  };

  const testSshConnection = async () => {
    if (!connected) {
      return;
    }
    try {
      const result = await client.testSshConnection({
        host: settings.sshHost,
        user: settings.sshUser,
        remote_path: settings.sshRemotePath,
        port: settings.sshPort || 22,
        identity_file: settings.sshIdentity || undefined,
      });
      setBlocks((prev) => [
        ...prev,
        {
          id: blockId(),
          kind: result.ok ? "meta" : "error",
          text:
            locale === "ru"
              ? `SSH: ${result.ok ? "OK" : "ошибка"} — ${result.detail}`
              : `SSH: ${result.ok ? "OK" : "failed"} — ${result.detail}`,
        },
      ]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    }
  };

  const buildRunPayload = (input: string, runMode: "ask" | "agent" = "agent") => {
    const useSsh =
      settings.executionMode === "ssh" ||
      (settings.executionMode === "hybrid" && settings.sshHost.trim());
    return {
      input,
      session_id: settings.sessionId || undefined,
      project_id: projectId || undefined,
      changed_files: attachmentPaths(attachments),
      policy_preset: effectivePolicyPresetFromSettings(),
      execution_mode: settings.executionMode,
      workspace_scope: settings.workspace || undefined,
      retrieval_path_prefix: settings.workspace || undefined,
      run_mode: runMode,
      auto_confirm_risky_tools: true,
      verify_after_patch: true,
      use_tool_loop: true,
      ...(useSsh
        ? {
            ssh_host: settings.sshHost.trim(),
            ssh_user: settings.sshUser.trim(),
            ssh_port: settings.sshPort || 22,
            ssh_identity: settings.sshIdentity.trim() || undefined,
            ssh_remote_path: settings.sshRemotePath.trim(),
          }
        : {}),
    };
  };

  const effectivePolicyPresetFromSettings = () =>
    settings.agentRunMode === "autopilot" ? "autopilot" : settings.policyPreset || undefined;

  const buildAgentInputFromChat = (message: string) => {
    const recent = blocks
      .filter((block) => block.kind === "user" || block.kind === "assistant")
      .slice(-6);
    if (recent.length === 0) {
      return message;
    }
    const transcript = recent.map((block) => `${block.kind}: ${block.text}`).join("\n\n");
    return `${transcript}\n\n[user follow-up]\n${message}`;
  };

  const sendAskChat = async (fullMessage: string) => {
    const assistantId = blockId();
    setBlocks((prev) => [
      ...prev,
      {
        id: assistantId,
        kind: "assistant",
        text: locale === "ru" ? "Думаю…" : "Thinking…",
      },
    ]);
    let responseText = "";
    try {
      for await (const event of client.chatStream({
        message: fullMessage,
        task_type: settings.taskType,
        session_id: settings.sessionId || undefined,
        model: settings.selectedModel || undefined,
        repo_profile: settings.repoProfile || undefined,
        use_retrieval: settings.useRetrieval,
        use_repo_map: Boolean(projectId),
        use_context_packing: true,
        changed_files: attachmentPaths(attachments),
        project_id: projectId || undefined,
        retrieval_path_prefix: workspacePrefix(settings.workspace),
      })) {
        if (event.event === "meta") {
          const nextSession = String(event.data.session_id ?? "");
          if (nextSession) {
            updateSettings({ sessionId: nextSession });
          }
        } else if (event.event === "token") {
          responseText += String(event.data.text ?? "");
          setBlocks((prev) =>
            prev.map((block) =>
              block.id === assistantId ? { ...block, text: responseText || "…" } : block
            )
          );
        }
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) =>
        prev.map((block) => (block.id === assistantId ? { ...block, kind: "error", text } : block))
      );
    }
  };

  const importCursorRules = async () => {
    if (!connected || !projectId || rulesSaving) {
      return;
    }
    setRulesSaving(true);
    try {
      const rules = await client.importCursorProjectRules(projectId, {
        workspace_root: settings.workspace,
      });
      setProjectRulesText(rules.project_rules ?? "");
      setStatusLine(
        locale === "ru"
          ? `Импортированы Cursor rules для ${projectId}`
          : `Imported Cursor rules for ${projectId}`
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatusLine(text);
    } finally {
      setRulesSaving(false);
    }
  };

  const refreshAgentRuns = async (agentId: string) => {
    const response = await client.listAgentRuns(agentId, 15);
    setAgentRuns(response.runs);
  };

  const refreshPlatformData = async (agentId?: string | null) => {
    try {
      const [skills, schedules, mcp, hooks, search] = await Promise.all([
        client.listPlatformSkills(),
        client.listPlatformSchedules(agentId ?? undefined),
        client.listPlatformMcpServers(),
        client.getPlatformHooksStatus(),
        client.getPlatformSearchStatus(),
      ]);
      setPlatformSkills(skills.skills.map((item) => ({ skill_id: item.skill_id, name: item.name })));
      setPlatformSchedules(
        schedules.schedules.map((item) => ({
          schedule_id: item.schedule_id,
          agent_id: item.agent_id,
          cron: item.cron,
          enabled: item.enabled,
        }))
      );
      setPlatformMcpServers(
        mcp.servers.map((item) => ({
          server_id: item.server_id,
          name: item.name,
          command: item.command,
          enabled: item.enabled,
        }))
      );
      setPlatformStatus(
        [
          `hooks: ${hooks.enabled ? "on" : "off"} (${hooks.configured_events.length} events)`,
          `search: ${search.provider}${search.configured ? "" : " (offline stub)"}`,
          `skills: ${skills.skills.length}`,
          `mcp servers: ${mcp.servers.length}`,
          `schedules: ${schedules.schedules.length}`,
        ].join(" · ")
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setPlatformStatus(text);
    }
  };

  const refreshRunSpans = async (runId: string) => {
    try {
      const response = await client.listRunSpans(runId, 50);
      if (response.spans.length === 0) {
        setRunSpansText(`No spans recorded for ${runId}.`);
        return;
      }
      setRunSpansText(
        response.spans
          .map(
            (span) =>
              `${span.name} · ${span.duration_ms}ms\n  ${span.detail.slice(0, 200)}`
          )
          .join("\n\n")
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setRunSpansText(text);
    }
  };

  const confirmAgentRun = async (approved: boolean) => {
    if (!awaitingConfirmationRunId) {
      return;
    }
    try {
      const result = await client.confirmAgentRun(awaitingConfirmationRunId, approved);
      setAwaitingConfirmationRunId(null);
      if (result.resumed) {
        setWatchedRunId(result.run_id);
      } else {
        setWatchedRunId(null);
        setWatchedRunState(null);
        if (selectedAgentId) {
          await refreshAgentRuns(selectedAgentId);
        }
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setAgentTimeline(text);
    }
  };

  const resumeAgentRun = async () => {
    if (!watchedRunId) {
      return;
    }
    const started = Date.now();
    try {
      const result = await client.resumeAgentRun(watchedRunId);
      setWatchedRunId(result.run_id);
      setWatchedRunState(result.state);
      setAgentTimeline(`Resumed run ${result.run_id} (${result.state})`);
      trackWorkflowEvent(client, {
        event_type: "agent_resume",
        journey_id: settings.activeJourneyId,
        duration_ms: Date.now() - started,
        ok: true,
        detail: result.run_id,
      });
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setAgentTimeline(text);
      trackWorkflowEvent(client, {
        event_type: "agent_resume",
        journey_id: settings.activeJourneyId,
        duration_ms: Date.now() - started,
        ok: false,
        detail: text,
      });
    }
  };

  const saveMcpServer = async () => {
    if (!mcpDraftName.trim() || !mcpDraftCommand.trim()) {
      return;
    }
    setMcpSaving(true);
    try {
      await client.upsertPlatformMcpServer({
        name: mcpDraftName.trim(),
        command: mcpDraftCommand.trim(),
        args: mcpDraftArgs
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        enabled: true,
      });
      setMcpDraftName("");
      setMcpDraftCommand("");
      setMcpDraftArgs("");
      await refreshPlatformData(selectedAgentId);
      setPlatformStatus("MCP server saved.");
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setPlatformStatus(text);
    } finally {
      setMcpSaving(false);
    }
  };

  const importCursorMcp = async () => {
    if (!connected || mcpImportBusy) {
      return;
    }
    setMcpImportBusy(true);
    try {
      const result = await client.importPlatformCursorMcp({ workspace_root: settings.workspace });
      await refreshPlatformData(selectedAgentId);
      setPlatformStatus(
        locale === "ru"
          ? `Импортировано MCP из .cursor/mcp.json: ${result.imported}`
          : `Imported MCP from .cursor/mcp.json: ${result.imported}`
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setPlatformStatus(text);
    } finally {
      setMcpImportBusy(false);
    }
  };

  const toggleProjectSkill = (skillId: string) => {
    setSelectedProjectSkills((prev) =>
      prev.includes(skillId) ? prev.filter((item) => item !== skillId) : [...prev, skillId]
    );
  };

  useEffect(() => {
    if (!watchedRunId || !connected) {
      return;
    }
    void refreshRunSpans(watchedRunId);
    const abort = new AbortController();
    void watchAgentRun(
      client,
      watchedRunId,
      ({ run, events }) => {
        setAgentTimeline(formatAgentTimeline(run, events));
        setWatchedRunState(run.state);
        setToolStepCount(countToolSteps(events));
        if (run.state === "awaiting_confirmation") {
          setAwaitingConfirmationRunId(run.run_id);
          return;
        }
        setAwaitingConfirmationRunId(null);
        void client.getAgentRun(run.run_id).then((record) => {
          setCheckpointLine(parseCheckpointSummary(record.checkpoint_json));
        });
        if (run.state === "completed") {
          window.termitDesktop.showNotification({
            title: "Agent run completed",
            body: `${run.run_id} · ${selectedAgentId ?? "agent"}`,
          });
          setWatchedRunId(null);
          setWatchedRunState(null);
          if (selectedAgentId) {
            void refreshAgentRuns(selectedAgentId);
          }
        } else if (run.state === "failed") {
          window.termitDesktop.showNotification({
            title: "Agent run failed",
            body: `${run.run_id} · ${selectedAgentId ?? "agent"}`,
          });
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
    if (!connected) {
      return;
    }
    void refreshLiveChanges();
    const timer = window.setInterval(() => void refreshLiveChanges(), 4000);
    return () => window.clearInterval(timer);
  }, [connected, client]);

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
        { kind: "file", path: relativePath, excerpt: file.content },
      ]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    }
  };

  const attachFolder = async () => {
    if (!settings.workspace) {
      return;
    }
    const folder = window.prompt(t(locale, "promptFolder"), "app");
    if (!folder?.trim()) {
      return;
    }
    try {
      const response = await client.listFiles({ path: folder.trim(), pattern: "*" });
      const files = response.files.filter((file) => !file.endsWith("/")).slice(0, 8);
      const next: ContextAttachment[] = [];
      for (const file of files) {
        const content = await client.readFile({ path: file, max_bytes: 8000 });
        next.push({ kind: "folder", path: file, excerpt: content.content, label: folder.trim() });
      }
      setAttachments((prev) => [...prev, ...next]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    }
  };

  const attachSymbol = async () => {
    const query = window.prompt(t(locale, "promptSymbol"));
    if (!query?.trim()) {
      return;
    }
    try {
      const prefix = workspacePrefix(settings.workspace);
      const result = await client.searchSymbols({
        query: query.trim(),
        limit: 5,
        path_prefix: prefix || undefined,
      });
      const next: ContextAttachment[] = [];
      for (const match of result.matches.slice(0, 5)) {
        const file = await client.readFile({ path: match.path, max_bytes: 12000 });
        next.push({
          kind: "symbol",
          path: match.path,
          label: `${match.name} (${match.kind})`,
          excerpt: excerptAroundLine(file.content, match.line),
        });
      }
      if (next.length === 0) {
        setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text: `No symbols for "${query}"` }]);
        return;
      }
      setAttachments((prev) => [...prev, ...next]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    }
  };

  const attachDocs = async () => {
    try {
      const docs: ContextAttachment[] = [];
      for (const path of ["README.md", "START_HERE_RU.md", "docs"]) {
        try {
          if (path === "docs") {
            const listed = await client.listFiles({ path: "docs", pattern: "*.md" });
            for (const file of listed.files.slice(0, 4)) {
              const content = await client.readFile({ path: file, max_bytes: 8000 });
              docs.push({ kind: "docs", path: file, label: file, excerpt: content.content });
            }
            continue;
          }
          const content = await client.readFile({ path, max_bytes: 12000 });
          docs.push({ kind: "docs", path, label: path, excerpt: content.content });
        } catch {
          continue;
        }
      }
      if (docs.length === 0) {
        setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text: "No docs found (README.md / docs/)" }]);
        return;
      }
      setAttachments((prev) => [...prev, ...docs]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    }
  };

  const attachWeb = async () => {
    const query = window.prompt(t(locale, "promptWeb"));
    if (!query?.trim()) {
      return;
    }
    try {
      const result = await client.searchWeb(query.trim(), 5);
      const excerpt = result.hits
        .map((hit, index) => `[${index + 1}] ${hit.title}\n${hit.url}\n${hit.snippet}`)
        .join("\n\n");
      setAttachments((prev) => [
        ...prev,
        {
          kind: "web",
          path: result.provider,
          label: query.trim(),
          excerpt: excerpt || "No web results.",
        },
      ]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    }
  };

  const pullOllamaModel = async (model: string) => {
    setPullingModel(model);
    try {
      await client.pullOllamaModel(model);
      const localStatus = await client.localRuntimeStatus();
      setMissingOllamaModels(localStatus.missing_ollama_models ?? []);
      setStatusLine(`Pulled ${model}`);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatusLine(text);
    } finally {
      setPullingModel(null);
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
    const composerStarted = Date.now();
    let responseText = "";
    const scopedPaths =
      composerMode === "component" && composerFiles.length > 0
        ? [composerFiles[0].path]
        : composerFiles.map((item) => item.path);
    if (composerMode === "component" && composerFiles.length !== 1) {
      setComposerLog(
        locale === "ru"
          ? "Режим компонента: добавьте ровно один @file."
          : "Component mode: attach exactly one @file."
      );
      setComposerBusy(false);
      return;
    }
    const composerMessage =
      composerMode === "component" && composerFiles.length === 1
        ? buildComponentComposerMessage(instruction, composerFiles[0])
        : buildComposerMessage(instruction, composerFiles);
    try {
      for await (const event of client.chatStream({
        message: composerMessage,
        task_type: "coding",
        session_id: settings.sessionId || undefined,
        model: settings.selectedModel || undefined,
        repo_profile: settings.repoProfile || undefined,
        use_retrieval: true,
        use_repo_map: Boolean(projectId),
        use_context_packing: composerFiles.length > 0,
        changed_files: composerFiles.map((item) => item.path),
        project_id: projectId || undefined,
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
      let patches = parseComposerPatches(responseText);
      if (composerMode === "component" && scopedPaths.length > 0) {
        patches = filterComposerPatchesToPaths(patches, scopedPaths);
      }
      setComposerPatches(patches);
      setComposerPatchPreviews({});
      setComposerBackups({});
      const previews = await dryRunAllPatches(client, patches);
      setComposerPatchPreviews(previews);
      setSafeApplySummary(summarizePatchRisk(patches, previews));
      if (composerFiles.length > 0 || patches.length > 0) {
        const suggestions = await suggestContextFiles(client, {
          changedFiles: [
            ...composerFiles.map((item) => item.path),
            ...patches.map((item) => item.path),
          ],
          workspacePrefix: workspacePrefix(settings.workspace),
          limit: 6,
        });
        setContextSuggestions(suggestions);
      } else {
        setContextSuggestions([]);
      }
      const prose = stripComposerJsonBlock(responseText);
      setComposerLog(
        `${prose}\n\n---\nParsed ${patches.length} patch(es). Click a file to dry-run preview.`
      );
      trackWorkflowEvent(client, {
        event_type: "composer_generated",
        journey_id: settings.activeJourneyId,
        execution_mode: settings.executionMode,
        duration_ms: Date.now() - composerStarted,
        ok: patches.length > 0,
        detail: `${patches.length} patches`,
      });
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
    if (safeApplySummary && !safeApplySummary.canApplyAll) {
      setComposerPatchDetail(
        formatSafeApplyHint(safeApplySummary, locale) +
          (safeApplySummary.blockedPaths.length
            ? `\n${safeApplySummary.blockedPaths.join(", ")}`
            : "")
      );
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
    trackWorkflowEvent(client, {
      event_type: "composer_applied",
      journey_id: settings.activeJourneyId,
      execution_mode: settings.executionMode,
      ok: applied > 0 && errors.length === 0,
      detail: `applied ${applied}/${composerPatches.length}`,
    });
    if (applied > 0 && pendingVerifyCommands.length > 0) {
      setBlocks((prev) => [
        ...prev,
        {
          id: blockId(),
          kind: "meta",
          text:
            locale === "ru"
              ? `Патчи применены. Verify: ${pendingVerifyCommands.join(" · ")}`
              : `Patches applied. Verify: ${pendingVerifyCommands.join(" · ")}`,
        },
      ]);
    }
  };

  const applyComposerPatch = async (patch: ApplyPatchRequest) => {
    const backups: Record<string, string> = { ...composerBackups };
    if (backups[patch.path] === undefined) {
      try {
        const existing = await client.readFile({ path: patch.path, max_bytes: 500_000 });
        backups[patch.path] = existing.content;
      } catch {
        backups[patch.path] = "";
      }
      setComposerBackups(backups);
    }
    try {
      const result = await client.applyPatch({ ...patch, confirmed: true, dry_run: false });
      setComposerLog((prev) =>
        `${prev}\n\n${result.applied ? "Applied" : "Skipped"} ${patch.path}${result.policy_reason ? `: ${result.policy_reason}` : ""}`
      );
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setComposerPatchDetail(text);
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

  const saveProjectRules = async () => {
    if (!connected || !projectId || rulesSaving) {
      return;
    }
    setRulesSaving(true);
    try {
      await client.saveProjectRules(projectId, {
        project_rules: projectRulesText,
        user_rules: userRulesText,
        skills: selectedProjectSkills,
      });
      setStatusLine(`Project rules saved for ${projectId}`);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatusLine(text);
    } finally {
      setRulesSaving(false);
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
    created.agentFolder = selectedFolder || activeAgentLabel || "General";
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

  const saveSessionRename = (localId: string) => {
    const next = renameSession(chatSessions, localId, renameDraft);
    saveChatSessions(next);
    setChatSessions(next);
    setRenamingSessionId(null);
    setRenameDraft("");
  };

  const moveSessionToFolder = (localId: string, folder: string) => {
    const cleaned = folder.trim() || "General";
    const next = chatSessions.map((session) =>
      session.localId === localId ? { ...session, agentFolder: cleaned, updatedAt: Date.now() } : session
    );
    saveChatSessions(next);
    setChatSessions(next);
  };

  const createFolder = () => {
    const name = folderDraft.trim();
    if (!name) {
      return;
    }
    setSelectedFolder(name);
    setFolderDraft("");
  };

  const refreshLiveChanges = async (): Promise<GitChange[]> => {
    if (!connected) {
      return [];
    }
    setLiveChangesLoading(true);
    setLiveChangesError("");
    try {
      const result = await client.executeCommand({
        command: "git status --porcelain",
        path: ".",
        confirmed: true,
        dry_run: false,
        timeout_seconds: 20,
      });
      if (!result.executed) {
        setLiveChangesError(result.policy_reason ?? "git status blocked");
        setLiveChanges([]);
        return [];
      }
      const parsed = parseGitPorcelain(result.stdout ?? "");
      setLiveChanges(parsed);
      try {
        const statResult = await client.executeCommand({
          command: "git diff --shortstat",
          path: ".",
          confirmed: true,
          dry_run: false,
          timeout_seconds: 20,
        });
        if (statResult.executed) {
          setReviewStats(parseGitShortstat(statResult.stdout ?? ""));
        }
      } catch {
        setReviewStats({ added: 0, deleted: 0 });
      }
      if (!selectedChangePath && parsed[0]?.path) {
        setSelectedChangePath(parsed[0].path);
      }
      return parsed;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setLiveChangesError(text);
      setLiveChanges([]);
      return [];
    } finally {
      setLiveChangesLoading(false);
    }
  };

  const openLiveChange = async (path: string) => {
    setSelectedChangePath(path);
    try {
      const [diff, content] = await Promise.all([
        client.executeCommand({
          command: `git diff -- "${path}"`,
          path: ".",
          confirmed: true,
          dry_run: false,
          timeout_seconds: 20,
        }),
        client.readFile({ path, max_bytes: 12000 }).catch(() => ({ content: "" })),
      ]);
      const diffText = (diff.stdout || diff.stderr || "").trim();
      const body = [
        `Path: ${path}`,
        "",
        diffText ? `Diff:\n${diffText}` : "Diff is empty (maybe new/untracked).",
        content.content ? `\n\nCurrent file:\n${content.content}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      setSelectedChangePreview(body);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setSelectedChangePreview(text);
    }
  };

  const filteredSessions = useMemo(() => {
    const query = sessionSearch.trim().toLowerCase();
    if (!query) {
      return chatSessions;
    }
    return chatSessions.filter(
      (session) =>
        session.title.toLowerCase().includes(query) ||
        session.summary.toLowerCase().includes(query)
    );
  }, [chatSessions, sessionSearch]);

  const activeChatTitle = useMemo(() => {
    const active = chatSessions.find((session) => session.localId === activeLocalId);
    return active?.title || (locale === "ru" ? "Новый агент" : "New Agent");
  }, [chatSessions, activeLocalId, locale]);

  const sendChat = async () => {
    const message = draft.trim();
    if (!message || busy) {
      return;
    }

    if (!connected) {
      const ready = await ensureApiReady();
      if (!ready) {
        setBlocks((prev) => [
          ...prev,
          { id: blockId(), kind: "user", text: message },
          {
            id: blockId(),
            kind: "error",
            text:
              locale === "ru"
                ? "Termit API offline. Укажите repo Termit в мастере или ⚙ → auto-start сервера."
                : "Termit API offline. Set Termit repo in wizard or ⚙ → auto-start server.",
          },
        ]);
        setDraft(message);
        if (!isFirstRunComplete()) {
          setShowWizard(true);
        } else {
          setSettingsOpen(true);
        }
        return;
      }
    }

    if (isBuildTask(message) && !settings.workspace.trim()) {
      setBlocks((prev) => [
        ...prev,
        { id: blockId(), kind: "user", text: message },
        {
          id: blockId(),
          kind: "meta",
          text:
            locale === "ru"
              ? "Выберите workspace в ⚙ настройках — без него агент не сможет писать файлы."
              : "Pick a workspace in ⚙ settings — required for agent file writes.",
        },
      ]);
      setSettingsOpen(true);
      return;
    }

    const fullMessage = buildMessageWithAttachments(message, attachments);
    setDraft("");
    const currentAttachments = attachments;
    setAttachments([]);
    setBusy(true);
    setBlocks((prev) => [...prev, { id: blockId(), kind: "user", text: fullMessage }]);

    try {
      const input = buildMessageWithAttachments(fullMessage, currentAttachments);
      setAgentInput(input);
      if (settings.chatInteractionMode === "ask") {
        await sendAskChat(input);
      } else {
        await runAgent(input, undefined, "agent");
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
    } finally {
      setBusy(false);
    }
  };

  const runChatAsAgent = async () => {
    const message = draft.trim();
    if (!message || busy) {
      return;
    }
    const contextual = buildAgentInputFromChat(buildMessageWithAttachments(message, attachments));
    setDraft("");
    setAttachments([]);
    setBusy(true);
    setBlocks((prev) => [
      ...prev,
      { id: blockId(), kind: "user", text: buildMessageWithAttachments(message, attachments) },
      {
        id: blockId(),
        kind: "meta",
        text:
          locale === "ru"
            ? "Запуск agent run с контекстом чата…"
            : "Starting agent run with chat context…",
      },
    ]);
    try {
      await runAgent(contextual, undefined, "agent");
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

  const runAgent = async (
    inputOverride?: string,
    agentIdOverride?: string,
    runMode: "ask" | "agent" = "agent"
  ) => {
    const input = (inputOverride ?? agentInput).trim();
    if (!input) {
      setBlocks((prev) => [
        ...prev,
        {
          id: blockId(),
          kind: "error",
          text: locale === "ru" ? "Введите задачу для агента." : "Enter a task for the agent.",
        },
      ]);
      return;
    }

    const agentId = await resolveAgentIdForRun(agentIdOverride, input);
    if (!agentId) {
      setBlocks((prev) => [
        ...prev,
        {
          id: blockId(),
          kind: "error",
          text:
            locale === "ru"
              ? "Не удалось найти или создать агента. Проверьте API и шаблон web-app-vite."
              : "Could not find or create an agent. Check API and web-app-vite template.",
        },
      ]);
      return;
    }

    const effectivePolicyPreset = effectivePolicyPresetFromSettings();
    const runMetaId = blockId();
    const runTapeId = blockId();
    const runOutputId = blockId();
    const runSuggestionsId = blockId();

    setBlocks((prev) => [
      ...prev,
      {
        id: runMetaId,
        kind: "meta",
        text:
          locale === "ru"
            ? `Запускаю агента «${agents.find((a) => a.agent_id === agentId)?.name ?? agentId}» · режим ${settings.executionMode}${isBuildTask(input) ? " · plan→research→scaffold→build" : ""}…`
            : `Starting agent «${agents.find((a) => a.agent_id === agentId)?.name ?? agentId}» · mode ${settings.executionMode}${isBuildTask(input) ? " · plan→research→scaffold→build" : ""}…`,
      },
      {
        id: runTapeId,
        kind: "tape",
        text:
          locale === "ru"
            ? "⏳ Лента выполнения: подготовка run…"
            : "⏳ Activity tape: preparing run…",
      },
      {
        id: runOutputId,
        kind: "assistant",
        text: locale === "ru" ? "Ожидаю ответ агента…" : "Waiting for agent response…",
      },
    ]);

    let run;
    try {
      run = await client.createAgentRun(agentId, buildRunPayload(input, runMode));
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) =>
        prev.map((block) => {
          if (block.id === runMetaId) {
            return { ...block, kind: "error", text: locale === "ru" ? "Run не создан" : "Run not created" };
          }
          if (block.id === runTapeId) {
            return { ...block, text: text };
          }
          if (block.id === runOutputId) {
            return { ...block, kind: "error", text };
          }
          return block;
        })
      );
      return;
    }

    setBlocks((prev) =>
      prev.map((block) =>
        block.id === runMetaId
          ? { ...block, text: `Agent run: ${run.run_id} (${run.state})` }
          : block
      )
    );
    trackWorkflowEvent(client, {
      event_type: "agent_run_created",
      journey_id: settings.activeJourneyId,
      execution_mode: settings.executionMode,
      detail: run.run_id,
    });
    setAgentDetail(`Run queued: ${run.run_id} (${run.state})`);
    if (!inputOverride) {
      setAgentInput("");
    }
    setWatchedRunId(run.run_id);
    void refreshAgentRuns(agentId);
    void refreshLiveChanges();

    let lastEvents: AgentRunEvent[] = [];

    try {
      await watchAgentRun(
        client,
        run.run_id,
        ({ run: live, events }) => {
          lastEvents = events;
          const tapeText = formatActivityTape(locale, live, events);
          setBlocks((prev) =>
            prev.map((block) => {
              if (block.id === runMetaId) {
                return { ...block, text: `Agent run: ${run.run_id} · ${live.state}` };
              }
              if (block.id === runTapeId) {
                return { ...block, text: tapeText };
              }
              if (block.id === runOutputId) {
                const last = events[events.length - 1];
                const liveLine = last
                  ? `[${live.state}] ${last.event_type}: ${last.message}`
                  : `[${live.state}]`;
                if (live.response?.trim()) {
                  return { ...block, text: live.response.trim() };
                }
                return {
                  ...block,
                  text:
                    locale === "ru"
                      ? `Агент работает…\n${liveLine}`
                      : `Agent is working…\n${liveLine}`,
                };
              }
              return block;
            })
          );
          if (events.length > 0 && events.length % 2 === 0) {
            void refreshLiveChanges();
          }
        },
        { pollMs: 500, timeoutSeconds: 900 }
      );

      const finalRun = await client.getAgentRun(run.run_id);
      if (lastEvents.length === 0) {
        lastEvents = await client.getAgentRunEvents(run.run_id);
      }
      const latestChanges = await refreshLiveChanges();
      const finalTape = formatActivityTape(locale, finalRun, lastEvents);
      const finalText =
        finalRun.response?.trim() ||
        (locale === "ru"
          ? `Run завершён: ${finalRun.state}`
          : `Run finished: ${finalRun.state}`);
      const completion = buildCompletionSuggestions(locale, finalRun, lastEvents, latestChanges);

      setBlocks((prev) => {
        const hasSuggestions = prev.some((block) => block.id === runSuggestionsId);
        const next = prev.map((block) => {
          if (block.id === runMetaId) {
            return { ...block, text: `Agent run: ${run.run_id} · ${finalRun.state}` };
          }
          if (block.id === runTapeId) {
            return { ...block, text: finalTape };
          }
          if (block.id === runOutputId) {
            return { ...block, text: finalText };
          }
          return block;
        });
        if (!hasSuggestions) {
          next.push({
            id: runSuggestionsId,
            kind: "suggestions",
            text: completion.text,
            actions: completion.actions,
          });
        }
        return next;
      });
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setBlocks((prev) =>
        prev.map((block) => {
          if (block.id === runMetaId) {
            return { ...block, kind: "error", text: `Agent run: ${run.run_id} · failed` };
          }
          if (block.id === runTapeId) {
            return { ...block, text: `${block.text}\n\n✗ ${text}` };
          }
          if (block.id === runOutputId) {
            return { ...block, kind: "error", text };
          }
          return block;
        })
      );
    }
  };

  const dispatchFollowUp = (prompt: string) => {
    setDraft(prompt);
    void (async () => {
      setBusy(true);
      setBlocks((prev) => [...prev, { id: blockId(), kind: "user", text: prompt }]);
      try {
        await runAgent(prompt);
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        setBlocks((prev) => [...prev, { id: blockId(), kind: "error", text }]);
      } finally {
        setBusy(false);
      }
    })();
  };

  const runJourneyWithAgent = async (journey: DesktopJourney) => {
    if (!connected) {
      return;
    }
    let agentId = selectedAgentId;
    if (!agentId && agents.length > 0) {
      agentId = agents[0].agent_id;
      setSelectedAgentId(agentId);
    }
    if (!agentId) {
      setBlocks((prev) => [
        ...prev,
        {
          id: blockId(),
          kind: "error",
          text:
            locale === "ru"
              ? "Не удалось выбрать агента — будет создан автоматически при отправке задачи."
              : "No agent selected — one will be created automatically when you send a task.",
        },
      ]);
      return;
    }
    trackWorkflowEvent(client, {
      event_type: "journey_started",
      journey_id: journey.journey_id,
      execution_mode: settings.executionMode,
    });
    const title = journeyTitle(journey, locale);
    const desc = journeyDescription(journey, locale);
    const steps = journey.steps.map((step) => `- ${stepLabel(locale, step)}`).join("\n");
    const journeyPolicy =
      settings.agentRunMode === "autopilot"
        ? "autopilot"
        : settings.policyPreset || "default";
    const input =
      locale === "ru"
        ? `Выполни North Star сценарий «${title}».\n\nОписание: ${desc}\n\nШаги:\n${steps}\n\nWorkspace: ${settings.workspace || "(не выбран)"}\nРежим: ${settings.executionMode}\nPolicy: ${journeyPolicy}\n\nДоведи задачу до verify и краткого отчёта. Используй tool loop, apply_patch с preview, post-patch verify.`
        : `Execute North Star journey "${title}".\n\nDescription: ${desc}\n\nSteps:\n${steps}\n\nWorkspace: ${settings.workspace || "(not set)"}\nMode: ${settings.executionMode}\nPolicy: ${journeyPolicy}\n\nComplete through verify and a short report. Use tool loop, apply_patch with preview, post-patch verify.`;
    setAgentInput(input);
    updateSettings({ activeJourneyId: journey.journey_id });
    setDraft(input);
    await runAgent(input, agentId);
  };

  return (
    <div className="cursor-app">
      {showWizard && (
        <FirstRunWizard
          settings={settings}
          healthLine={wizardHealth}
          busy={busy}
          locale={locale}
          missingOllamaModels={missingOllamaModels}
          pullingModel={pullingModel}
          onUpdate={updateSettings}
          onPickRepo={() => void pickRepoRoot()}
          onPickWorkspace={() => void pickWorkspace()}
          onConnect={() => void ensureApiReady()}
          onToggleAutoStartServer={(enabled) => void toggleAutoStartServer(enabled)}
          onPullModel={(model) => void pullOllamaModel(model)}
          onComplete={async () => {
            await syncLauncherConfig();
            if (settings.autoStartServer && settings.repoRoot.trim()) {
              await window.termitDesktop.ensureServer(settings.baseUrl);
            }
            if (settings.autoConnect) {
              await connect();
            }
            markFirstRunComplete();
            setShowWizard(false);
          }}
        />
      )}
      <nav className="cursor-rail" aria-label="Termit">
        <button
          type="button"
          className="cursor-rail-btn primary"
          title={locale === "ru" ? "Новый агент" : "New Agent"}
          onClick={newChatSession}
        >
          +
        </button>
        {!connected ? (
          <button
            type="button"
            className="cursor-rail-btn"
            title={t(locale, "connect")}
            onClick={() => void connect()}
          >
            ⎔
          </button>
        ) : null}
        <button
          type="button"
          className="cursor-rail-btn"
          title={locale === "ru" ? "Настройки" : "Settings"}
          onClick={() => setSettingsOpen(true)}
        >
          ⚙
        </button>
        <div className="cursor-rail-spacer" />
        <span
          className={`cursor-rail-dot ${connected ? "ok" : apiReachable ? "ok" : "bad"}`}
          title={statusLine}
        />
      </nav>

      <aside className="cursor-sidebar" aria-label="Agent chats">
        <div className="cursor-sidebar-top">
          <h2>Termit</h2>
          <input
            className="cursor-sidebar-search"
            placeholder={t(locale, "searchSessions")}
            value={sessionSearch}
            onChange={(event) => setSessionSearch(event.target.value)}
          />
        </div>
        <div className="cursor-sidebar-list">
          {chatFolders.map((folder) => (
            <div key={folder.id} className="cursor-sidebar-folder">
              <div className="cursor-sidebar-folder-name">{folder.label}</div>
              {folder.sessions
                .filter((session) =>
                  !sessionSearch.trim()
                    ? true
                    : `${session.title} ${session.summary}`
                        .toLowerCase()
                        .includes(sessionSearch.trim().toLowerCase())
                )
                .map((session) => (
                  <button
                    key={session.localId}
                    type="button"
                    className={`cursor-thread ${activeLocalId === session.localId ? "active" : ""}`}
                    onClick={() => switchChatSession(session.localId)}
                  >
                    <div className="cursor-thread-title">{session.title}</div>
                    {session.summary ? (
                      <div className="cursor-thread-meta">{session.summary}</div>
                    ) : null}
                  </button>
                ))}
            </div>
          ))}
        </div>
      </aside>

      {settingsOpen ? (
        <div className="cursor-settings-backdrop" onClick={() => setSettingsOpen(false)}>
          <aside
            className="cursor-settings-panel sidebar"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="cursor-settings-header">
              <strong>{locale === "ru" ? "Настройки Termit" : "Termit Settings"}</strong>
              <button type="button" className="secondary compact" onClick={() => setSettingsOpen(false)}>
                ×
              </button>
            </div>
        <p className="hint">{t(locale, "appSubtitle")}</p>

        <div className="field">
          <label htmlFor="locale">{t(locale, "locale")}</label>
          <select
            id="locale"
            value={settings.locale}
            onChange={(event) => updateSettings({ locale: event.target.value as "ru" | "en" })}
          >
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </div>

        <div className={`status-pill ${connected ? "connected" : apiReachable ? "reachable" : ""}`}>
          {connected ? statusLine : apiReachable ? t(locale, "apiReachable") : t(locale, "apiOffline")}
        </div>
        <div className="health-indicators" aria-label="Service health">
          <span className={`health-dot ${apiReachable ? "ok" : "bad"}`} title={t(locale, "termitApiTitle")} />
          API {apiReachable ? t(locale, "apiOnline") : t(locale, "apiOfflineShort")}
          <span className={`health-dot ${ollamaOk === true ? "ok" : ollamaOk === false ? "bad" : "unknown"}`} title={t(locale, "ollamaTitle")} />
          Ollama {ollamaOk === true ? t(locale, "ollamaOk") : ollamaOk === false ? t(locale, "ollamaDown") : t(locale, "ollamaUnknown")}
          {termitVersion && <span className="version-tag">v{termitVersion}</span>}
        </div>

        <div className="field">
          <label htmlFor="workspace">{t(locale, "workspaceFolder")}</label>
          <input id="workspace" value={settings.workspace} readOnly />
          <button type="button" className="secondary" onClick={() => void pickWorkspace()}>
            {t(locale, "chooseFolder")}
          </button>
        </div>

        <div className="field">
          <label htmlFor="sidebarAgent">{locale === "ru" ? "Агент" : "Agent"}</label>
          <select
            id="sidebarAgent"
            value={selectedAgentId ?? ""}
            onChange={(event) => setSelectedAgentId(event.target.value || null)}
          >
            <option value="">{locale === "ru" ? "Автовыбор" : "Auto"}</option>
            {agents.map((agent) => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="executionModeMain">{t(locale, "executionMode")}</label>
          <select
            id="executionModeMain"
            value={settings.executionMode}
            onChange={(event) =>
              updateSettings({
                executionMode: event.target.value as StoredSettings["executionMode"],
              })
            }
          >
            <option value="hybrid">{executionModeLabel(locale, "hybrid")}</option>
            <option value="local">{executionModeLabel(locale, "local")}</option>
            <option value="online">{executionModeLabel(locale, "online")}</option>
            <option value="ssh">{executionModeLabel(locale, "ssh")}</option>
          </select>
          <span className="hint">
            {locale === "ru"
              ? "Hybrid: plan → research online → файлы локально/SSH → verify → preview."
              : "Hybrid: plan → online research → files local/SSH → verify → preview."}
          </span>
        </div>

        {(settings.executionMode === "ssh" || settings.executionMode === "hybrid") && (
          <div className="ssh-panel">
            <div className="field">
              <label htmlFor="sshHost">SSH host</label>
              <input
                id="sshHost"
                value={settings.sshHost}
                placeholder="203.0.113.10"
                onChange={(event) => updateSettings({ sshHost: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="sshUser">SSH user</label>
              <input
                id="sshUser"
                value={settings.sshUser}
                placeholder="deploy"
                onChange={(event) => updateSettings({ sshUser: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="sshRemotePath">{locale === "ru" ? "Путь на сервере" : "Remote path"}</label>
              <input
                id="sshRemotePath"
                value={settings.sshRemotePath}
                placeholder="/var/www/app"
                onChange={(event) => updateSettings({ sshRemotePath: event.target.value })}
              />
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="sshPort">Port</label>
                <input
                  id="sshPort"
                  type="number"
                  value={settings.sshPort}
                  onChange={(event) =>
                    updateSettings({ sshPort: Number(event.target.value) || 22 })
                  }
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="sshIdentity">{locale === "ru" ? "SSH ключ (-i)" : "Identity file (-i)"}</label>
              <input
                id="sshIdentity"
                value={settings.sshIdentity}
                placeholder="~/.ssh/id_ed25519"
                onChange={(event) => updateSettings({ sshIdentity: event.target.value })}
              />
            </div>
            <button
              type="button"
              className="secondary compact"
              disabled={!connected}
              onClick={() => void testSshConnection()}
            >
              {locale === "ru" ? "Проверить SSH" : "Test SSH"}
            </button>
          </div>
        )}

        <div className="row">
          <button type="button" className="primary" onClick={() => void connect()}>
            {connected ? t(locale, "refreshConnection") : t(locale, "connect")}
          </button>
        </div>

        <details className="settings-collapsible">
          <summary>{locale === "ru" ? "Расширенные настройки" : "Advanced settings"}</summary>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoExecuteWithAgent}
            onChange={(event) => updateSettings({ autoExecuteWithAgent: event.target.checked })}
          />
          {t(locale, "autoExecuteAgent")}
        </label>
        <p className="hint">{t(locale, "autoExecuteAgentHint")}</p>

        <div className="field">
          <label htmlFor="baseUrl">{t(locale, "apiUrl")}</label>
          <input
            id="baseUrl"
            value={settings.baseUrl}
            onChange={(event) => updateSettings({ baseUrl: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="apiKey">{t(locale, "apiKey")}</label>
          <input
            id="apiKey"
            type="password"
            value={settings.apiKey}
            placeholder={t(locale, "apiKeyPlaceholder")}
            onChange={(event) => updateSettings({ apiKey: event.target.value })}
          />
          <span className="hint">{t(locale, "apiKeyHint")}</span>
        </div>

        <div className="field">
          <label htmlFor="repoRoot">{t(locale, "repoRoot")}</label>
          <input id="repoRoot" value={settings.repoRoot} readOnly placeholder="/path/to/Termit" />
          <button type="button" className="secondary" onClick={() => void pickRepoRoot()}>
            {t(locale, "chooseRepo")}
          </button>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoStartServer}
            onChange={(event) => void toggleAutoStartServer(event.target.checked)}
          />
          {t(locale, "autoStartServer")}
        </label>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.autoConnect}
            onChange={(event) => updateSettings({ autoConnect: event.target.checked })}
          />
          {t(locale, "connectOnLaunch")}
        </label>

        <div className="row">
          <button type="button" className="secondary" onClick={() => void startServer()}>
            {t(locale, "startServerNow")}
          </button>
        </div>

        <p className="hint">
          <a href={settings.baseUrl} target="_blank" rel="noreferrer">
            {t(locale, "wizardOpenWebDashboard")}
          </a>
        </p>

        <div className="field">
          <label htmlFor="taskType">{t(locale, "defaultTaskType")}</label>
          <select
            id="taskType"
            value={settings.taskType}
            onChange={(event) =>
              updateSettings({ taskType: event.target.value as TaskType })
            }
          >
            <option value="coding">{t(locale, "taskTypeCoding")}</option>
            <option value="review">{t(locale, "taskTypeReview")}</option>
            <option value="debug">{t(locale, "taskTypeDebug")}</option>
            <option value="explain">{t(locale, "taskTypeExplain")}</option>
            <option value="general">{t(locale, "taskTypeGeneral")}</option>
          </select>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.useRetrieval}
            onChange={(event) => updateSettings({ useRetrieval: event.target.checked })}
          />
          {t(locale, "useRetrieval")}
        </label>
        <div className="row retrieval-row">
          <span className="badge">{retrievalMode}</span>
          <button
            type="button"
            className="secondary compact"
            disabled={!connected || reindexBusy}
            onClick={() => void reindexCodebase()}
          >
            {reindexBusy ? t(locale, "reindexing") : t(locale, "reindex")}
          </button>
        </div>

        {projectId && (
          <div className="field project-rules">
            <label htmlFor="projectRules">
              {t(locale, "projectRules")} ({projectId})
            </label>
            <textarea
              id="projectRules"
              rows={4}
              value={projectRulesText}
              placeholder={t(locale, "projectRulesPlaceholder")}
              onChange={(event) => setProjectRulesText(event.target.value)}
            />
            <label htmlFor="userRules">{t(locale, "userRules")}</label>
            <textarea
              id="userRules"
              rows={2}
              value={userRulesText}
              placeholder={t(locale, "userRulesPlaceholder")}
              onChange={(event) => setUserRulesText(event.target.value)}
            />
            <button
              type="button"
              className="secondary compact"
              disabled={!connected || rulesSaving}
              onClick={() => void importCursorRules()}
            >
              {t(locale, "importCursorRules")}
            </button>
            <label>{t(locale, "projectSkillsLabel")}</label>
            {platformSkills.length > 0 ? (
              <div className="platform-skill-grid">
                {platformSkills.map((skill) => (
                  <label key={skill.skill_id} className="checkbox-row compact">
                    <input
                      type="checkbox"
                      checked={selectedProjectSkills.includes(skill.skill_id)}
                      onChange={() => toggleProjectSkill(skill.skill_id)}
                    />
                    {skill.name}
                  </label>
                ))}
              </div>
            ) : (
              <p className="hint">{t(locale, "noPlatformSkills")}</p>
            )}
            <button
              type="button"
              className="secondary compact"
              disabled={!connected || rulesSaving}
              onClick={() => void saveProjectRules()}
            >
              {rulesSaving ? t(locale, "saving") : t(locale, "saveRules")}
            </button>
          </div>
        )}

        <details className="settings-collapsible nested">
          <summary>{locale === "ru" ? "Platform / MCP / ops" : "Platform / MCP / ops"}</summary>

        <div className="field platform-panel">
          <label>{t(locale, "platformPanelLabel")}</label>
          <p className="hint">{platformStatus || t(locale, "platformNotLoaded")}</p>
          <div className="row">
            <button
              type="button"
              className="secondary compact"
              disabled={!connected}
              onClick={() => void refreshPlatformData(selectedAgentId)}
            >
              {t(locale, "refreshPlatform")}
            </button>
          </div>

          <label>{t(locale, "skillsLabel")}</label>
          {platformSkills.length > 0 ? (
            <ul className="muted compact-list">
              {platformSkills.map((skill) => (
                <li key={skill.skill_id}>
                  {skill.name} · {skill.skill_id}
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">{t(locale, "noPlatformSkills")}</p>
          )}

          <label>{t(locale, "schedulesLabel")}</label>
          {platformSchedules.length > 0 ? (
            <ul className="muted compact-list">
              {platformSchedules.map((item) => (
                <li key={item.schedule_id}>
                  {item.cron} · {item.agent_id} {item.enabled ? "" : t(locale, "mcpDisabled")}
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">{t(locale, "noSchedules")}</p>
          )}

          <label>{t(locale, "traceSpansLabel")}</label>
          <pre className="platform-spans">{runSpansText || t(locale, "runSpansPlaceholder")}</pre>
        </div>

        <div className="field">
          <label>{t(locale, "mcpServers")}</label>
          {platformMcpServers.length > 0 ? (
            <ul className="muted compact-list">
              {platformMcpServers.map((item) => (
                <li key={item.server_id}>
                  {item.name} · {item.command} {item.enabled ? "" : t(locale, "mcpDisabled")}
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">{t(locale, "noMcp")}</p>
          )}
          <input
            value={mcpDraftName}
            placeholder={t(locale, "mcpServerNamePlaceholder")}
            onChange={(event) => setMcpDraftName(event.target.value)}
          />
          <input
            value={mcpDraftCommand}
            placeholder={t(locale, "mcpCommandPlaceholder")}
            onChange={(event) => setMcpDraftCommand(event.target.value)}
          />
          <input
            value={mcpDraftArgs}
            placeholder={t(locale, "mcpArgsPlaceholder")}
            onChange={(event) => setMcpDraftArgs(event.target.value)}
          />
          <div className="row">
            <button
              type="button"
              className="secondary compact"
              disabled={!connected || mcpSaving}
              onClick={() => void saveMcpServer()}
            >
              {mcpSaving ? t(locale, "saving") : t(locale, "addMcp")}
            </button>
            <button
              type="button"
              className="secondary compact"
              disabled={!connected || mcpImportBusy}
              onClick={() => void importCursorMcp()}
            >
              {mcpImportBusy ? t(locale, "saving") : t(locale, "importCursorMcp")}
            </button>
            <button
              type="button"
              className="secondary compact"
              disabled={!connected}
              onClick={() => void refreshPlatformData(selectedAgentId)}
            >
              {t(locale, "refreshMcp")}
            </button>
          </div>
        </div>
        </details>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.inlineCompletionEnabled}
            onChange={(event) => updateSettings({ inlineCompletionEnabled: event.target.checked })}
          />
          {t(locale, "tabCompletion")}
        </label>

        {repoProfiles.length > 0 && (
          <div className="field">
            <label htmlFor="repoProfile">{t(locale, "repoProfile")}</label>
            <select
              id="repoProfile"
              value={settings.repoProfile}
              onChange={(event) => updateSettings({ repoProfile: event.target.value })}
            >
              <option value="">{t(locale, "noneOption")}</option>
              {repoProfiles.map((profile) => (
                <option key={profile.profile_id} value={profile.profile_id}>
                  {profile.title}
                  {profile.finetuned ? t(locale, "finetunedBadge") : ""} → {profile.preferred_model}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="field">
          <label htmlFor="agentRunMode">{t(locale, "agentRunMode")}</label>
          <select
            id="agentRunMode"
            value={settings.agentRunMode}
            onChange={(event) =>
              updateSettings({
                agentRunMode: event.target.value as StoredSettings["agentRunMode"],
              })
            }
          >
            <option value="guided">{t(locale, "agentRunModeGuided")}</option>
            <option value="autopilot">{t(locale, "agentRunModeAutopilot")}</option>
          </select>
          <p className="hint">
            {t(
              locale,
              settings.agentRunMode === "autopilot"
                ? "agentRunModeAutopilotHint"
                : "agentRunModeGuidedHint"
            )}
          </p>
        </div>

        <PolicyPresetSelector
          presets={policyPresets}
          value={settings.agentRunMode === "autopilot" ? "autopilot" : settings.policyPreset}
          locale={locale}
          disabled={!connected || settings.agentRunMode === "autopilot"}
          onChange={(presetId) => updateSettings({ policyPreset: presetId })}
        />

        <MediaStudioPanel client={client} connected={connected} locale={locale} />

        <div className="field">
          <label htmlFor="model">{t(locale, "model")}</label>
          <select
            id="model"
            value={settings.selectedModel}
            onChange={(event) => updateSettings({ selectedModel: event.target.value })}
          >
            <option value="">{t(locale, "modelAuto")}</option>
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>
        </details>
          </aside>
        </div>
      ) : null}

      <section className="cursor-main">
        <header className="cursor-titlebar">
          <h1>{activeChatTitle}</h1>
          <span className="cursor-mode-badge">{settings.executionMode}</span>
          {!connected ? (
            <button type="button" className="secondary compact" onClick={() => void ensureApiReady()}>
              {t(locale, "connect")}
            </button>
          ) : null}
        </header>

        <div className="cursor-chat-scroll" ref={chatLogRef}>
              {blocks.length === 0 ? (
                <div className="cursor-empty-state">
                  {locale === "ru" ? (
                    <>
                      Опишите задачу — Termit спланирует, закодирует, проверит и покажет diff справа.
                      <br />
                      <br />
                      <kbd>Enter</kbd> отправить · <kbd>Shift+Enter</kbd> новая строка · ⚙ workspace / SSH
                    </>
                  ) : (
                    <>
                      Describe your task — Termit plans, codes, verifies, and shows diffs on the right.
                      <br />
                      <br />
                      <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> newline · ⚙ workspace / SSH
                    </>
                  )}
                </div>
              ) : (
                blocks.map((block) => (
                  <div key={block.id} className={`message-block ${block.kind}`}>
                    {block.kind === "user" && <strong>{t(locale, "you")}</strong>}
                    {block.kind === "assistant" && <strong>{t(locale, "termit")}</strong>}
                    {block.kind === "tape" && (
                      <strong>{locale === "ru" ? "Лента выполнения" : "Activity tape"}</strong>
                    )}
                    {block.kind === "suggestions" && (
                      <strong>{locale === "ru" ? "Итог и рекомендации" : "Summary & next steps"}</strong>
                    )}
                    {block.kind === "error" && <strong>{t(locale, "error")}</strong>}
                    {block.kind === "meta" && <strong>{t(locale, "info")}</strong>}
                    {"\n"}
                    {block.text}
                    {block.kind === "suggestions" && block.actions && block.actions.length > 0 ? (
                      <div className="chips suggestion-actions">
                        {block.actions.map((action) => (
                          <button
                            key={`${block.id}-${action}`}
                            type="button"
                            className="chip primary compact"
                            disabled={!connected || busy}
                            onClick={() => dispatchFollowUp(action)}
                          >
                            {action.length > 48 ? `${action.slice(0, 48)}…` : action}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
        </div>

        <footer className="cursor-footer">
          {busy ? (
            <div className="cursor-review-bar">
              {locale === "ru" ? "⏳ Агент работает…" : "⏳ Agent working…"}
            </div>
          ) : liveChanges.length > 0 || reviewStats.added > 0 || reviewStats.deleted > 0 ? (
            <div className="cursor-review-bar">
              <span>{locale === "ru" ? "Review" : "Review"}</span>
              {reviewStats.added > 0 ? (
                <span className="review-add">+{reviewStats.added}</span>
              ) : null}
              {reviewStats.deleted > 0 ? (
                <span className="review-del">-{reviewStats.deleted}</span>
              ) : null}
              <span className="review-files">
                {liveChanges.length} {locale === "ru" ? "файлов" : "files"}
              </span>
              <button
                type="button"
                className="secondary compact"
                disabled={!connected || liveChangesLoading}
                onClick={() => void refreshLiveChanges()}
              >
                ↻
              </button>
            </div>
          ) : null}

          {attachments.length > 0 ? (
            <div className="chips">
              {attachments.map((item) => (
                <span key={`${item.kind}-${item.path}-${item.label ?? ""}`} className="chip">
                  @{item.label ?? item.path}
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
          ) : null}

          <div className="cursor-composer">
            <textarea
              value={draft}
              placeholder={
                blocks.length > 0
                  ? locale === "ru"
                    ? "Send follow-up…"
                    : "Send follow-up…"
                  : locale === "ru"
                    ? "Создай сайт, API, программу… Termit сделает plan → code → verify"
                    : "Build a site, API, app… Termit runs plan → code → verify"
              }
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (draft.trim() && !busy) {
                    void sendChat();
                  }
                }
              }}
            />
            <div className="cursor-composer-toolbar">
              <button
                type="button"
                className="secondary compact"
                disabled={!connected}
                title={locale === "ru" ? "Прикрепить файл" : "Attach file"}
                onClick={() => void attachFile()}
              >
                +
              </button>
              <select
                value={settings.chatInteractionMode}
                onChange={(event) =>
                  updateSettings({
                    chatInteractionMode: event.target.value as StoredSettings["chatInteractionMode"],
                  })
                }
                title={t(locale, "chatInteractionMode")}
              >
                <option value="agent">{t(locale, "chatModeAgent")}</option>
                <option value="ask">{t(locale, "chatModeAsk")}</option>
              </select>
              <select
                value={selectedAgentId ?? ""}
                onChange={(event) => setSelectedAgentId(event.target.value || null)}
                title={locale === "ru" ? "Агент" : "Agent"}
              >
                <option value="">{locale === "ru" ? "Агент: авто" : "Agent: auto"}</option>
                {agents.map((agent) => (
                  <option key={agent.agent_id} value={agent.agent_id}>
                    {agent.name}
                  </option>
                ))}
              </select>
              <select
                value={settings.selectedModel}
                onChange={(event) => updateSettings({ selectedModel: event.target.value })}
                title={t(locale, "model")}
              >
                <option value="">{t(locale, "modelAuto")}</option>
                {models.map((model) => (
                  <option key={model} value={model}>
                    {model.replace(/^ollama:/, "")}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="secondary compact"
                disabled={!connected || busy || !draft.trim()}
                onClick={() => void runChatAsAgent()}
                title={t(locale, "runAsAgentHint")}
              >
                {t(locale, "runAsAgent")}
              </button>
              <button
                type="button"
                className="cursor-send-btn"
                disabled={!connected || busy || !draft.trim()}
                onClick={() => void sendChat()}
              >
                {busy
                  ? "…"
                  : settings.chatInteractionMode === "ask"
                    ? t(locale, "sendAsk")
                    : locale === "ru"
                      ? "Отправить"
                      : "Send"}
              </button>
            </div>
          </div>

          <div className="cursor-statusbar">
            <span>{workspacePrefix(settings.workspace) || (locale === "ru" ? "workspace не выбран" : "no workspace")}</span>
            <span>·</span>
            <span>{executionModeLabel(locale, settings.executionMode)}</span>
            <span>·</span>
            <span>{connected ? t(locale, "apiOnline") : t(locale, "apiOfflineShort")}</span>
          </div>
        </footer>
      </section>

      <aside className="cursor-review" aria-label="Review">
        <div className="cursor-review-header">
          <span>{locale === "ru" ? "Review" : "Review"}</span>
          <button
            type="button"
            className="secondary compact"
            disabled={!connected || liveChangesLoading}
            onClick={() => void refreshLiveChanges()}
          >
            ↻
          </button>
        </div>
        {liveChangesError ? <p className="hint error-text">{liveChangesError}</p> : null}
        <div className="changed-files-list">
          {liveChanges.length === 0 ? (
            <div className="muted changed-files-empty">
              {liveChangesLoading
                ? "…"
                : locale === "ru"
                  ? "Изменения появятся после патчей агента"
                  : "Changes appear after agent patches"}
            </div>
          ) : (
            liveChanges.map((item) => (
              <button
                key={`${item.status}-${item.path}`}
                type="button"
                className={`changed-files-item ${selectedChangePath === item.path ? "selected" : ""}`}
                title={item.path}
                onClick={() => void openLiveChange(item.path)}
              >
                <span className="git-status">{item.status}</span>
                {item.path}
              </button>
            ))
          )}
        </div>
        <pre className="detail-box live-change-preview">
          {selectedChangePreview ||
            (locale === "ru" ? "Выберите файл для diff." : "Select a file to view diff.")}
        </pre>
      </aside>
    </div>
  );
}
