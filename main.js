"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const node_path_1 = __importDefault(require("node:path"));
const serverLauncher_1 = require("./serverLauncher");
const isDev = !electron_1.app.isPackaged;
let mainWindow = null;
let tray = null;
function rendererIndexPath() {
    return node_path_1.default.join(electron_1.app.getAppPath(), "dist", "index.html");
}
function createWindow() {
    const window = new electron_1.BrowserWindow({
        width: 1280,
        height: 860,
        minWidth: 960,
        minHeight: 640,
        title: "Termit",
        webPreferences: {
            preload: node_path_1.default.join(__dirname, "preload.js"),
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
    }
    else {
        void window.loadFile(rendererIndexPath());
    }
    mainWindow = window;
    return window;
}
function trayIcon() {
    const size = process.platform === "darwin" ? 16 : 32;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="3" fill="#238636"/><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" fill="white" font-size="${Math.round(size * 0.55)}" font-family="sans-serif">T</text></svg>`;
    return electron_1.nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`);
}
function buildTrayMenu() {
    const userData = electron_1.app.getPath("userData");
    return electron_1.Menu.buildFromTemplate([
        {
            label: "Show Termit",
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                }
                else {
                    createWindow();
                }
            },
        },
        {
            label: "Restart server",
            click: () => {
                void (0, serverLauncher_1.restartServer)(userData).then((result) => {
                    if (mainWindow && !mainWindow.isDestroyed()) {
                        mainWindow.webContents.send("server:status", result);
                    }
                });
            },
        },
        {
            label: "Open logs",
            click: () => {
                void (0, serverLauncher_1.openLogs)(userData).then((result) => {
                    void electron_1.shell.showItemInFolder(result.message);
                });
            },
        },
        { type: "separator" },
        {
            label: "Quit Termit",
            click: () => {
                electron_1.app.quit();
            },
        },
    ]);
}
function createTray() {
    if (tray) {
        return;
    }
    tray = new electron_1.Tray(trayIcon());
    tray.setToolTip("Termit");
    tray.setContextMenu(buildTrayMenu());
    tray.on("click", () => {
        if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
        }
        else {
            createWindow();
        }
    });
}
async function maybeAutoStartServer() {
    const config = (0, serverLauncher_1.readLauncherConfig)(electron_1.app.getPath("userData"));
    if (!config.autoStartServer || !config.repoRoot) {
        return;
    }
    await (0, serverLauncher_1.ensureServer)(electron_1.app.getPath("userData"));
}
electron_1.app.whenReady().then(() => {
    if (process.platform === "darwin") {
        createTray();
    }
    void maybeAutoStartServer().finally(() => {
        createWindow();
    });
    electron_1.app.on("activate", () => {
        if (electron_1.BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});
electron_1.app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
        electron_1.app.quit();
    }
});
electron_1.ipcMain.handle("dialog:pickFile", async (_event, workspace) => {
    const result = await electron_1.dialog.showOpenDialog({
        defaultPath: workspace || undefined,
        properties: ["openFile"],
    });
    if (result.canceled || result.filePaths.length === 0) {
        return null;
    }
    const fullPath = result.filePaths[0];
    if (workspace && fullPath.startsWith(workspace)) {
        return node_path_1.default.relative(workspace, fullPath).replace(/\\/g, "/");
    }
    return fullPath;
});
electron_1.ipcMain.handle("dialog:pickWorkspace", async () => {
    const result = await electron_1.dialog.showOpenDialog({
        properties: ["openDirectory", "createDirectory"],
    });
    if (result.canceled || result.filePaths.length === 0) {
        return null;
    }
    return result.filePaths[0];
});
electron_1.ipcMain.handle("dialog:pickRepoRoot", async () => {
    const result = await electron_1.dialog.showOpenDialog({
        properties: ["openDirectory"],
        title: "Select Termit repository (contains app/ and .venv)",
    });
    if (result.canceled || result.filePaths.length === 0) {
        return null;
    }
    return result.filePaths[0];
});
electron_1.ipcMain.handle("launcher:getConfig", () => {
    return (0, serverLauncher_1.readLauncherConfig)(electron_1.app.getPath("userData"));
});
electron_1.ipcMain.handle("launcher:setConfig", (_event, config) => {
    (0, serverLauncher_1.writeLauncherConfig)(electron_1.app.getPath("userData"), config);
});
electron_1.ipcMain.handle("server:ensure", (_event, baseUrl) => {
    return (0, serverLauncher_1.ensureServer)(electron_1.app.getPath("userData"), baseUrl);
});
electron_1.ipcMain.handle("server:restart", () => {
    return (0, serverLauncher_1.restartServer)(electron_1.app.getPath("userData"));
});
electron_1.ipcMain.handle("logs:open", async () => {
    const result = await (0, serverLauncher_1.openLogs)(electron_1.app.getPath("userData"));
    return { ok: result.ok, path: result.message };
});
electron_1.ipcMain.on("notify:show", (_event, payload) => {
    if (!electron_1.Notification.isSupported()) {
        return;
    }
    new electron_1.Notification({ title: payload.title, body: payload.body }).show();
});
