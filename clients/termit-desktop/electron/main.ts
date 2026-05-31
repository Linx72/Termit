import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, Notification, shell, Tray } from "electron";
import path from "node:path";
import {
  ensureServer,
  openLogs,
  readLauncherConfig,
  restartServer,
  writeLauncherConfig,
  type LauncherConfig,
} from "./serverLauncher";

const isDev = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
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

  mainWindow = window;
  return window;
}

function trayIcon() {
  const size = process.platform === "darwin" ? 16 : 32;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="3" fill="#238636"/><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" fill="white" font-size="${Math.round(size * 0.55)}" font-family="sans-serif">T</text></svg>`;
  return nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`);
}

function buildTrayMenu(): Menu {
  const userData = app.getPath("userData");
  return Menu.buildFromTemplate([
    {
      label: "Show Termit",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        } else {
          createWindow();
        }
      },
    },
    {
      label: "Restart server",
      click: () => {
        void restartServer(userData).then((result) => {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send("server:status", result);
          }
        });
      },
    },
    {
      label: "Open logs",
      click: () => {
        void openLogs(userData).then((result) => {
          void shell.showItemInFolder(result.message);
        });
      },
    },
    { type: "separator" },
    {
      label: "Quit Termit",
      click: () => {
        app.quit();
      },
    },
  ]);
}

function createTray(): void {
  if (tray) {
    return;
  }
  tray = new Tray(trayIcon());
  tray.setToolTip("Termit");
  tray.setContextMenu(buildTrayMenu());
  tray.on("click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    } else {
      createWindow();
    }
  });
}

async function maybeAutoStartServer(): Promise<void> {
  const config = readLauncherConfig(app.getPath("userData"));
  if (!config.autoStartServer || !config.repoRoot) {
    return;
  }
  await ensureServer(app.getPath("userData"));
}

app.whenReady().then(() => {
  if (process.platform === "darwin") {
    createTray();
  }
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

ipcMain.handle("server:restart", () => {
  return restartServer(app.getPath("userData"));
});

ipcMain.handle("logs:open", async () => {
  const result = await openLogs(app.getPath("userData"));
  return { ok: result.ok, path: result.message };
});

ipcMain.on("notify:show", (_event, payload: { title: string; body: string }) => {
  if (!Notification.isSupported()) {
    return;
  }
  new Notification({ title: payload.title, body: payload.body }).show();
});
