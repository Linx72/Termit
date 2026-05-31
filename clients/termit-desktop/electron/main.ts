import { app, BrowserWindow, dialog, ipcMain } from "electron";
import path from "node:path";
import {
  ensureServer,
  readLauncherConfig,
  writeLauncherConfig,
  type LauncherConfig,
} from "./serverLauncher";

const isDev = !app.isPackaged;

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 900,
    minHeight: 640,
    title: "Termit",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (isDev) {
    void window.loadURL("http://127.0.0.1:5173");
    window.webContents.openDevTools({ mode: "detach" });
  } else {
    void window.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  return window;
}

async function maybeAutoStartServer(): Promise<void> {
  const config = readLauncherConfig(app.getPath("userData"));
  if (!config.autoStartServer || !config.repoRoot) {
    return;
  }
  await ensureServer(app.getPath("userData"));
}

app.whenReady().then(() => {
  void maybeAutoStartServer().finally(() => {
    createWindow();
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

ipcMain.handle("dialog:pickFile", async (_event, workspace: string) => {
  const result = await dialog.showOpenDialog({
    defaultPath: workspace || undefined,
    properties: ["openFile"],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  const fullPath = result.filePaths[0];
  if (workspace && fullPath.startsWith(workspace)) {
    return path.relative(workspace, fullPath).replace(/\\/g, "/");
  }
  return fullPath;
});

ipcMain.handle("dialog:pickWorkspace", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("dialog:pickRepoRoot", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
    title: "Select Termit repository (contains app/ and .venv)",
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("launcher:getConfig", () => {
  return readLauncherConfig(app.getPath("userData"));
});

ipcMain.handle("launcher:setConfig", (_event, config: LauncherConfig) => {
  writeLauncherConfig(app.getPath("userData"), config);
});

ipcMain.handle("server:ensure", (_event, baseUrl: string) => {
  return ensureServer(app.getPath("userData"), baseUrl);
});
