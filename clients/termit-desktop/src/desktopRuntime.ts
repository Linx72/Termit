import type {
  DocId,
  DocOpenResult,
  LauncherConfig,
  ServerEnsureResult,
  TermitDesktopApi,
} from "../shared/ipc";

const LAUNCHER_STORAGE_KEY = "termit-launcher-config";
export type DesktopRuntimePreference = "auto" | "desktop" | "web";

type DesktopRuntimeMode = "desktop" | "web";

interface DesktopRuntimeMeta {
  requested: DesktopRuntimePreference;
  mode: DesktopRuntimeMode;
  nativeAvailable: boolean;
  serverControl: boolean;
}

const WEB_DOC_URLS: Record<DocId, string> = {
  help: new URL("../docs/ru/TERMIT_HELP_RU.md", import.meta.url).href,
  training: new URL("../docs/ru/TERMIT_TRAINING_RU.md", import.meta.url).href,
};

function nativeDesktopApi(): TermitDesktopApi | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.termitDesktop ?? null;
}

let runtimePreference: DesktopRuntimePreference = "auto";

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
}

async function probeServer(baseUrl: string): Promise<ServerEnsureResult> {
  const normalized = normalizeBaseUrl(baseUrl || "http://127.0.0.1:8765");
  const endpoints = [`${normalized}/health`, `${normalized}/healthz`];
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, { method: "GET" });
      if (response.ok) {
        return { ok: true, message: `Server reachable: ${endpoint}` };
      }
    } catch {
      // Try next endpoint.
    }
  }
  return {
    ok: false,
    message: `Server is not reachable at ${normalized}`,
  };
}

function readLauncherConfig(): LauncherConfig {
  if (typeof localStorage === "undefined") {
    return { repoRoot: "", autoStartServer: false };
  }
  try {
    const raw = localStorage.getItem(LAUNCHER_STORAGE_KEY);
    if (!raw) {
      return { repoRoot: "", autoStartServer: false };
    }
    const parsed = JSON.parse(raw) as Partial<LauncherConfig>;
    return {
      repoRoot: parsed.repoRoot ?? "",
      autoStartServer: Boolean(parsed.autoStartServer),
    };
  } catch {
    return { repoRoot: "", autoStartServer: false };
  }
}

function writeLauncherConfig(config: LauncherConfig): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  localStorage.setItem(LAUNCHER_STORAGE_KEY, JSON.stringify(config));
}

async function openWebDoc(docId: DocId): Promise<DocOpenResult> {
  if (typeof window === "undefined") {
    return { ok: false, message: "Window is unavailable." };
  }
  const docUrl = WEB_DOC_URLS[docId];
  const opened = window.open(docUrl, "_blank", "noopener,noreferrer");
  if (!opened) {
    return { ok: false, message: "Browser blocked opening the document." };
  }
  return { ok: true, message: docUrl };
}

const webFallback: TermitDesktopApi = {
  pickWorkspace: async () => null,
  pickWorkspaceFile: async (_workspace: string) => null,
  pickRepoRoot: async () => null,
  getLauncherConfig: async () => readLauncherConfig(),
  setLauncherConfig: async (config: LauncherConfig) => {
    writeLauncherConfig(config);
  },
  ensureServer: async (baseUrl: string) => probeServer(baseUrl),
  showNotification: (payload) => {
    if (typeof window === "undefined") {
      return;
    }
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      new Notification(payload.title, { body: payload.body });
      return;
    }
    console.info(`[Termit] ${payload.title}: ${payload.body}`);
  },
  getDocFileUrl: async (docId: DocId) => WEB_DOC_URLS[docId],
  getDocPath: async (docId: DocId) => WEB_DOC_URLS[docId],
  openDocExternal: async (docId: DocId) => openWebDoc(docId),
};

function resolveRuntimeApi(): TermitDesktopApi {
  const native = nativeDesktopApi();
  if (runtimePreference === "web") {
    return webFallback;
  }
  if (runtimePreference === "desktop") {
    return native ?? webFallback;
  }
  return native ?? webFallback;
}

export function setDesktopRuntimePreference(preference: DesktopRuntimePreference): void {
  runtimePreference = preference;
}

export function getDesktopRuntimeMeta(): DesktopRuntimeMeta {
  const native = nativeDesktopApi();
  const mode: DesktopRuntimeMode =
    runtimePreference === "web" || (runtimePreference === "auto" && !native) ? "web" : "desktop";
  const isDesktop = mode === "desktop" && Boolean(native);
  return {
    requested: runtimePreference,
    mode,
    nativeAvailable: Boolean(native),
    serverControl: isDesktop,
  };
}

export const desktopRuntime: TermitDesktopApi = {
  getLauncherConfig: () => resolveRuntimeApi().getLauncherConfig(),
  setLauncherConfig: (config: LauncherConfig) => resolveRuntimeApi().setLauncherConfig(config),
  ensureServer: (baseUrl: string) => resolveRuntimeApi().ensureServer(baseUrl),
  showNotification: (payload) => resolveRuntimeApi().showNotification(payload),
  getDocFileUrl: (docId: DocId) => resolveRuntimeApi().getDocFileUrl(docId),
  getDocPath: (docId: DocId) => resolveRuntimeApi().getDocPath(docId),
  openDocExternal: (docId: DocId) => resolveRuntimeApi().openDocExternal(docId),
};
