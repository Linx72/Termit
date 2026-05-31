import { contextBridge, ipcRenderer } from "electron";
import type { TermitDesktopApi } from "../shared/ipc";

const api: TermitDesktopApi = {
  pickWorkspace: () => ipcRenderer.invoke("dialog:pickWorkspace") as Promise<string | null>,
  pickWorkspaceFile: (workspace: string) =>
    ipcRenderer.invoke("dialog:pickFile", workspace) as Promise<string | null>,
};

contextBridge.exposeInMainWorld("termitDesktop", api);
