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

export type DocId = "help" | "training";

export interface DocOpenResult {
  ok: boolean;
  message: string;
}

export interface TermitDesktopApi {
  getLauncherConfig(): Promise<LauncherConfig>;
  setLauncherConfig(config: LauncherConfig): Promise<void>;
  ensureServer(baseUrl: string): Promise<ServerEnsureResult>;
  showNotification(payload: DesktopNotificationPayload): void;
  getDocFileUrl(docId: DocId): Promise<string>;
  getDocPath(docId: DocId): Promise<string>;
  openDocExternal(docId: DocId): Promise<DocOpenResult>;
}

declare global {
  interface Window {
    termitDesktop: TermitDesktopApi;
  }
}

export {};
