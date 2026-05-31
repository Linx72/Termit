export interface LauncherConfig {
  repoRoot: string;
  autoStartServer: boolean;
}

export interface ServerEnsureResult {
  ok: boolean;
  message: string;
}

export interface DesktopNotificationPayload {
  title: string;
  body: string;
}

export interface TermitDesktopApi {
  pickWorkspace(): Promise<string | null>;
  pickWorkspaceFile(workspace: string): Promise<string | null>;
  pickRepoRoot(): Promise<string | null>;
  getLauncherConfig(): Promise<LauncherConfig>;
  setLauncherConfig(config: LauncherConfig): Promise<void>;
  ensureServer(baseUrl: string): Promise<ServerEnsureResult>;
  restartServer(): Promise<ServerEnsureResult>;
  openLogs(): Promise<{ ok: boolean; path: string }>;
  showNotification(payload: DesktopNotificationPayload): void;
}

declare global {
  interface Window {
    termitDesktop: TermitDesktopApi;
  }
}

export {};
