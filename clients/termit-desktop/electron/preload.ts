import { contextBridge, ipcRenderer } from "electron";
import type { DesktopNotificationPayload, DocId, DocOpenResult, LauncherConfig, TermitDesktopApi } from "../shared/ipc";

const api: TermitDesktopApi = {
  pickWorkspace: () => ipcRenderer.invoke("dialog:pickWorkspace") as Promise<string | null>,
  pickWorkspaceFile: (workspace: string) =>
    ipcRenderer.invoke("dialog:pickFile", workspace) as Promise<string | null>,
  pickRepoRoot: () => ipcRenderer.invoke("dialog:pickRepoRoot") as Promise<string | null>,
  getLauncherConfig: () => ipcRenderer.invoke("launcher:getConfig") as Promise<LauncherConfig>,
  setLauncherConfig: (config: LauncherConfig) =>
    ipcRenderer.invoke("launcher:setConfig", config) as Promise<void>,
  ensureServer: (baseUrl: string) =>
    ipcRenderer.invoke("server:ensure", baseUrl) as Promise<{ ok: boolean; message: string }>,
  restartServer: () =>
    ipcRenderer.invoke("server:restart") as Promise<{ ok: boolean; message: string }>,
  openLogs: () => ipcRenderer.invoke("logs:open") as Promise<{ ok: boolean; path: string }>,
  showNotification: (payload: DesktopNotificationPayload) => {
    ipcRenderer.send("notify:show", payload);
  },
  getDocFileUrl: (docId: DocId) => ipcRenderer.invoke("docs:fileUrl", docId) as Promise<string>,
  getDocPath: (docId: DocId) => ipcRenderer.invoke("docs:path", docId) as Promise<string>,
  openDocExternal: (docId: DocId) =>
    ipcRenderer.invoke("docs:openExternal", docId) as Promise<DocOpenResult>,
};

contextBridge.exposeInMainWorld("termitDesktop", api);
