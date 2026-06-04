import { app, BrowserWindow, ipcMain, Menu, nativeImage, Notification, shell, Tray } from "electron";
import path from "node:path";
import { pathToFileURL } from "node:url";
import type { DocId } from "../shared/ipc";
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

function rendererIndexPath(): string {
  return path.join(app.getAppPath(), "dist", "index.html");
}

const DOC_FILES: Record<DocId, string> = {
  help: "TERMIT_HELP_RU.pdf",
  training: "TERMIT_TRAINING_RU.pdf",
};

function docPdfPath(docId: DocId): string {
  return path.join(app.getAppPath(), "docs", "pdf", DOC_FILES[docId]);
}

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

  window.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`Renderer failed to load (${errorCode}): ${errorDescription} — ${validatedURL}`);
  });

  if (isDev) {
    void window.loadURL("http://127.0.0.1:5173");
    window.webContents.openDevTools({ mode: "detach" });
  } else {
    void window.loadFile(rendererIndexPath());
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

ipcMain.handle("launcher:getConfig", () => {
  return readLauncherConfig(app.getPath("userData"));
});

ipcMain.handle("launcher:setConfig", (_event, config: LauncherConfig) => {
  writeLauncherConfig(app.getPath("userData"), config);
});

ipcMain.handle("server:ensure", (_event, baseUrl: string) => {
  return ensureServer(app.getPath("userData"), baseUrl);
});

ipcMain.on("notify:show", (_event, payload: { title: string; body: string }) => {
  if (!Notification.isSupported()) {
    return;
  }
  new Notification({ title: payload.title, body: payload.body }).show();
});

ipcMain.handle("docs:fileUrl", (_event, docId: DocId) => {
  const filePath = docPdfPath(docId);
  return pathToFileURL(filePath).href;
});

ipcMain.handle("docs:path", (_event, docId: DocId) => docPdfPath(docId));

ipcMain.handle("docs:openExternal", async (_event, docId: DocId) => {
  const filePath = docPdfPath(docId);
  try {
    const result = await shell.openPath(filePath);
    if (result) {
      return { ok: false, message: result };
    }
    return { ok: true, message: filePath };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { ok: false, message };
  }
});
