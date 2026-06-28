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

// ── Whisper (голосовой ввод) ──────────────────────────────

export interface WhisperModelStatus {
  ready: boolean;
  model: string;
  path: string;
  sizeMb: number;
}

export interface WhisperStreamResult {
  partial: string;
  final: string;
  done: boolean;
}

export interface WhisperStartOptions {
  model?: string;
  language?: string;
}

// ── Brave Search ──────────────────────────────────────────

export interface BraveSearchResult {
  title: string;
  url: string;
  description: string;
  age?: string;
}

export interface BraveSearchResponse {
  query: string;
  results: BraveSearchResult[];
  total: number;
  error?: string;
}

export interface BraveSearchStatus {
  running: boolean;
  tools: string[];
  serverName: string;
}

export interface TermitDesktopApi {
  getLauncherConfig(): Promise<LauncherConfig>;
  setLauncherConfig(config: LauncherConfig): Promise<void>;
  ensureServer(baseUrl: string): Promise<ServerEnsureResult>;
  showNotification(payload: DesktopNotificationPayload): void;
  getDocFileUrl(docId: DocId): Promise<string>;
  getDocPath(docId: DocId): Promise<string>;
  openDocExternal(docId: DocId): Promise<DocOpenResult>;

  // ── Whisper ──
  whisperModelStatus(): Promise<WhisperModelStatus>;
  whisperDownloadModel(): Promise<{ ok: boolean; message: string }>;
  whisperStart(options?: WhisperStartOptions): Promise<{ ok: boolean; message: string }>;
  whisperStop(): Promise<{ text: string }>;
  whisperStream(audioChunk: ArrayBuffer): Promise<WhisperStreamResult>;

  // ── Brave Search ──
  braveSearch(query: string, count?: number): Promise<BraveSearchResponse>;
  braveSearchStatus(): Promise<BraveSearchStatus>;
  braveSearchStart(): Promise<{ ok: boolean; message: string }>;
  braveSearchStop(): Promise<void>;
}

declare global {
  interface Window {
    termitDesktop: TermitDesktopApi;
  }
}

export {};
