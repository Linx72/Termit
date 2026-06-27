import { contextBridge, ipcRenderer } from "electron";
import type {
  DesktopNotificationPayload,
  DocId,
  DocOpenResult,
  LauncherConfig,
  TermitDesktopApi,
  WhisperModelStatus,
  WhisperStartOptions,
  WhisperStreamResult,
} from "../shared/ipc";

const api: TermitDesktopApi = {
  // ── Существующие ──
  getLauncherConfig: () => ipcRenderer.invoke("launcher:getConfig") as Promise<LauncherConfig>,
  setLauncherConfig: (config: LauncherConfig) =>
    ipcRenderer.invoke("launcher:setConfig", config) as Promise<void>,
  ensureServer: (baseUrl: string) =>
    ipcRenderer.invoke("server:ensure", baseUrl) as Promise<{ ok: boolean; message: string }>,
  showNotification: (payload: DesktopNotificationPayload) => {
    ipcRenderer.send("notify:show", payload);
  },
  getDocFileUrl: (docId: DocId) => ipcRenderer.invoke("docs:fileUrl", docId) as Promise<string>,
  getDocPath: (docId: DocId) => ipcRenderer.invoke("docs:path", docId) as Promise<string>,
  openDocExternal: (docId: DocId) =>
    ipcRenderer.invoke("docs:openExternal", docId) as Promise<DocOpenResult>,

  // ── Whisper (голосовой ввод) ──
  whisperModelStatus: () =>
    ipcRenderer.invoke("whisper:modelStatus") as Promise<WhisperModelStatus>,
  whisperDownloadModel: (model?: string) =>
    ipcRenderer.invoke("whisper:downloadModel", model) as Promise<{ ok: boolean; message: string }>,
  whisperStart: (options?: WhisperStartOptions) =>
    ipcRenderer.invoke("whisper:start", options) as Promise<{ ok: boolean; message: string }>,
  whisperStop: () =>
    ipcRenderer.invoke("whisper:stop") as Promise<{ text: string }>,
  whisperStream: (audioChunk: ArrayBuffer) =>
    ipcRenderer.invoke("whisper:stream", audioChunk) as Promise<WhisperStreamResult>,
};

contextBridge.exposeInMainWorld("termitDesktop", api);
