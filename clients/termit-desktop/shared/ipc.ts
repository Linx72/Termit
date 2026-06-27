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
  partial: string;   // частичный результат (промежуточный)
  final: string;     // финальный текст после остановки
  done: boolean;
}

export interface WhisperStartOptions {
  model?: string;     // tiny / small / medium / large-v3
  language?: string;  // ru / en / auto
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
}

declare global {
  interface Window {
    termitDesktop: TermitDesktopApi;
  }
}

export {};
