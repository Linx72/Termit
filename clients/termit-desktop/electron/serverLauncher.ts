import { spawn, execFile, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export interface LauncherConfig {
  repoRoot: string;
  autoStartServer: boolean;
}

const DEFAULT_BASE_URL = "http://127.0.0.1:8765";

let serverProcess: ChildProcess | null = null;

export function configPath(userData: string): string {
  return path.join(userData, "termit-launcher.json");
}

export function readLauncherConfig(userData: string): LauncherConfig {
  const filePath = configPath(userData);
  if (!fs.existsSync(filePath)) {
    return { repoRoot: "", autoStartServer: false };
  }
  try {
    const raw = JSON.parse(fs.readFileSync(filePath, "utf8")) as Partial<LauncherConfig>;
    return {
      repoRoot: String(raw.repoRoot ?? ""),
      autoStartServer: Boolean(raw.autoStartServer),
    };
  } catch {
    return { repoRoot: "", autoStartServer: false };
  }
}

export function writeLauncherConfig(userData: string, config: LauncherConfig): void {
  fs.writeFileSync(configPath(userData), JSON.stringify(config, null, 2), "utf8");
}

export async function checkHealth(baseUrl: string = DEFAULT_BASE_URL): Promise<boolean> {
  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/health`, {
      signal: AbortSignal.timeout(2500),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function ensureServer(
  userData: string,
  baseUrl: string = DEFAULT_BASE_URL
): Promise<{ ok: boolean; message: string }> {
  if (await checkHealth(baseUrl)) {
    return { ok: true, message: "Termit server already running" };
  }

  const config = readLauncherConfig(userData);
  if (!config.repoRoot || !fs.existsSync(config.repoRoot)) {
    return {
      ok: false,
      message: "Set Termit repo path in sidebar (folder with .venv and app/)",
    };
  }

  const uvicorn = path.join(config.repoRoot, ".venv/bin/uvicorn");
  if (!fs.existsSync(uvicorn)) {
    return {
      ok: false,
      message: `Missing venv at ${config.repoRoot}/.venv — run: python3 -m venv .venv && pip install -r requirements.txt`,
    };
  }

  if (serverProcess && !serverProcess.killed) {
    await new Promise((resolve) => setTimeout(resolve, 800));
    if (await checkHealth(baseUrl)) {
      return { ok: true, message: "Started Termit server" };
    }
  }

  serverProcess = spawn(
    uvicorn,
    ["app.main:app", "--host", "127.0.0.1", "--port", "8765"],
    {
      cwd: config.repoRoot,
      detached: true,
      stdio: "ignore",
    }
  );
  serverProcess.unref();

  for (let attempt = 0; attempt < 20; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    if (await checkHealth(baseUrl)) {
      return { ok: true, message: "Termit server started on :8765" };
    }
  }

  return {
    ok: false,
    message: "Server did not respond on :8765 — check .venv and Ollama",
  };
}

export function resolveLogPaths(userData: string): string[] {
  const config = readLauncherConfig(userData);
  const paths: string[] = [];
  const homeLogDir = path.join(os.homedir(), "Library", "Logs", "Termit");
  paths.push(homeLogDir);
  if (config.repoRoot) {
    paths.push(path.join(config.repoRoot, ".tools", "termit-launchd.log"));
    paths.push(path.join(config.repoRoot, ".tools", "termit-launchd.err.log"));
    paths.push(path.join(config.repoRoot, ".tools", "termit-server.log"));
  }
  return paths;
}

export async function openLogs(userData: string): Promise<{ ok: boolean; message: string }> {
  const logDir = path.join(os.homedir(), "Library", "Logs", "Termit");
  fs.mkdirSync(logDir, { recursive: true });
  for (const candidate of resolveLogPaths(userData)) {
    if (candidate === logDir) {
      continue;
    }
    if (fs.existsSync(candidate)) {
      return { ok: true, message: candidate };
    }
  }
  return { ok: true, message: logDir };
}

export async function restartServer(userData: string): Promise<{ ok: boolean; message: string }> {
  const config = readLauncherConfig(userData);
  if (!config.repoRoot || !fs.existsSync(config.repoRoot)) {
    return { ok: false, message: "Set Termit repo path first." };
  }
  const script = path.join(config.repoRoot, "scripts", "restart_server.sh");
  if (!fs.existsSync(script)) {
    return { ok: false, message: `Missing ${script}` };
  }
  try {
    await execFileAsync(script, { cwd: config.repoRoot, timeout: 120_000 });
    const healthy = await checkHealth();
    return healthy
      ? { ok: true, message: "Termit server restarted on :8765" }
      : { ok: false, message: "Restart script ran but health check failed." };
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error);
    return { ok: false, message: text };
  }
}
