export type TaskType = "coding" | "review" | "debug" | "explain" | "general";

export type ActivityFeedDetail = "compact" | "detailed" | "verbose";

export interface StoredSettings {
  baseUrl: string;
  apiKey: string;
  sessionId: string;
  workspace: string;
  repoRoot: string;
  autoStartServer: boolean;
  autoConnect: boolean;
  taskType: TaskType;
  useRetrieval: boolean;
  selectedModel: string;
  repoProfile: string;
  inlineCompletionEnabled: boolean;
  activityFeedEnabled: boolean;
  activityFeedDetail: ActivityFeedDetail;
  locale: import("./i18n").Locale;
  policyPreset: string;
  teamName: string;
  activeJourneyId: string;
  executionMode: "local" | "online" | "hybrid" | "ssh";
  agentRunMode: "guided" | "autopilot";
  chatInteractionMode: "ask" | "agent" | "plan" | "terminal";
  autoExecuteWithAgent: boolean;
  sshHost: string;
  sshUser: string;
  sshPort: number;
  sshIdentity: string;
  sshRemotePath: string;
  runtimeMode: "auto" | "desktop" | "web";
  defaultAgentTemplate: string;
  mcpContextInject: boolean;
  autoSelectSkills: boolean;
}

export const STORAGE_KEY = "termit-app-settings";
export const FIRST_RUN_KEY = "termit-first-run-done";

export function loadSettings(): StoredSettings {
  const defaults: StoredSettings = {
    baseUrl: "http://127.0.0.1:8765",
    apiKey: "",
    sessionId: "",
    workspace: "",
    repoRoot: "",
    autoStartServer: true,
    autoConnect: true,
    taskType: "coding",
    useRetrieval: true,
    selectedModel: "",
    repoProfile: "",
    inlineCompletionEnabled: false,
    activityFeedEnabled: true,
    activityFeedDetail: "detailed",
    locale: "ru",
    policyPreset: "solo",
    teamName: "default",
    activeJourneyId: "local_feature",
    executionMode: "hybrid",
    agentRunMode: "guided",
    chatInteractionMode: "agent",
    autoExecuteWithAgent: true,
    sshHost: "",
    sshUser: "",
    sshPort: 22,
    sshIdentity: "",
    sshRemotePath: "",
    runtimeMode: "auto",
    defaultAgentTemplate: "desktop-cursor-parity-stable",
    mcpContextInject: true,
    autoSelectSkills: true,
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

export function saveSettings(settings: StoredSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function isFirstRunComplete(): boolean {
  return localStorage.getItem(FIRST_RUN_KEY) === "1";
}

export function markFirstRunComplete(): void {
  localStorage.setItem(FIRST_RUN_KEY, "1");
}
