import { contextBridge, ipcRenderer } from "electron";
import type { DesktopNotificationPayload, DocId, DocOpenResult, LauncherConfig, TermitDesktopApi } from "../shared/ipc";

const api: TermitDesktopApi = {
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
};

contextBridge.exposeInMainWorld("termitDesktop", api);
