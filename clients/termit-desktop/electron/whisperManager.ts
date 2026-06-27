/**
 * WhisperManager — управление whisper.cpp subprocess для локального
 * распознавания речи через Apple Neural Engine (CoreML) на macOS.
 *
 * Архитектура:
 *   микрофон → PCM 16kHz mono → stdin pipe → whisper-cli → stdout → текст
 *
 * Модель скачивается один раз в userData/whisper-models/.
 * whisper.cpp собирается отдельно (см. scripts/build-whisper.sh).
 */

import { app } from "electron";
import { ChildProcess, spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdir, stat, access, constants } from "node:fs/promises";
import { get } from "node:https";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import type { WhisperModelStatus, WhisperStreamResult } from "../shared/ipc";

// ── Константы ──────────────────────────────────────────────

const WHISPER_BIN = path.join(
  app.getAppPath(),
  "whisper.cpp",
  "build",
  "bin",
  "whisper-cli"
);

const WHISPER_STREAM_BIN = path.join(
  app.getAppPath(),
  "whisper.cpp",
  "build",
  "bin",
  "whisper-stream"
);

const MODELS_DIR = path.join(app.getPath("userData"), "whisper-models");

const MODEL_DOWNLOADS: Record<string, { url: string; sizeMb: number }> = {
  tiny: {
    url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    sizeMb: 78,
  },
  small: {
    url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    sizeMb: 466,
  },
  medium: {
    url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    sizeMb: 1530,
  },
  "large-v3": {
    url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
    sizeMb: 3100,
  },
};
const MODELS_DIR = path.join(app.getPath("userData"), "whisper-models");

// Альтернативная директория моделей (рядом с whisper.cpp, для dev-режима)
const DEV_MODELS_DIR = path.join(app.getAppPath(), "whisper.cpp", "models");

// ── Утилиты ────────────────────────────────────────────────

function modelPath(model: string): string {
  return path.join(MODELS_DIR, `ggml-${model}.bin`);
}

function devModelPath(model: string): string {
  return path.join(DEV_MODELS_DIR, `ggml-${model}.bin`);
}

/** Найти модель — сначала userData, потом dev-директория */
async function findModel(model: string): Promise<string | null> {
  const mp = modelPath(model);
  if (await fileExists(mp)) return mp;
  const dmp = devModelPath(model);
  if (await fileExists(dmp)) return dmp;
  return null;
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await access(filePath, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

// ── WhisperManager ──────────────────────────────────────────

export class WhisperManager {
  private proc: ChildProcess | null = null;
  private model: string = DEFAULT_MODEL;
  private stdout = "";
  private resolveStop: ((text: string) => void) | null = null;

  /** Проверить статус модели */
  async modelStatus(): Promise<WhisperModelStatus> {
    const found = await findModel(this.model);
    let sizeMb = 0;
    let modelPathStr = modelPath(this.model);
    if (found) {
      modelPathStr = found;
      const st = await stat(found);
      sizeMb = Math.round(st.size / (1024 * 1024));
    }
    return {
      ready: !!found,
      model: this.model,
      path: modelPathStr,
      sizeMb,
    };
  }

  /** Скачать модель с HuggingFace */
  async downloadModel(model?: string): Promise<{ ok: boolean; message: string }> {
    const mdl = model ?? this.model;
    const mp = modelPath(mdl);
    const download = MODEL_DOWNLOADS[mdl];

    if (!download) {
      return { ok: false, message: `Unknown model: ${mdl}` };
    }

    if (await fileExists(mp)) {
      return { ok: true, message: `Model already exists: ${mp}` };
    }

    try {
      await mkdir(MODELS_DIR, { recursive: true });

      console.log(`[Whisper] Downloading model ${mdl} (${download.sizeMb} MB)…`);

      await new Promise<void>((resolve, reject) => {
        const file = createWriteStream(mp);
        get(download.url, (response) => {
          // Редирект
          if (response.statusCode && response.statusCode >= 300 && response.statusCode < 400) {
            const redirectUrl = response.headers.location;
            if (!redirectUrl) {
              reject(new Error("Redirect without location"));
              return;
            }
            // Следуем редиректу
            get(redirectUrl, (res2) => {
              pipeline(res2, file)
                .then(resolve)
                .catch(reject);
            }).on("error", reject);
            return;
          }
          pipeline(response, file).then(resolve).catch(reject);
        }).on("error", reject);
      });

      console.log(`[Whisper] Model ${mdl} downloaded.`);
      return { ok: true, message: `Downloaded ${mdl} (${download.sizeMb} MB)` };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, message };
    }
  }

  /** Запустить whisper.cpp в режиме ожидания stdin */
  async start(options?: { model?: string; language?: string }): Promise<{ ok: boolean; message: string }> {
    if (this.proc) {
      await this.stop();
    }

    const mdl = options?.model ?? this.model;
    const lang = options?.language ?? "auto";
    const mp = modelPath(mdl);

    // Проверить, есть ли модель
    if (!(await fileExists(mp))) {
      return {
        ok: false,
        message: `Model not found: ${mp}. Download it first.`,
      };
    }

    // Проверить, есть ли бинарник
    if (!(await fileExists(WHISPER_BIN))) {
      return {
        ok: false,
        message: `whisper-cli not found at ${WHISPER_BIN}. Run build-whisper.sh first.`,
      };
    }

    this.model = mdl;
    this.stdout = "";

    // whisper-cli читает PCM 16kHz 16bit mono из stdin
    // и пишет текст в stdout
    const args = [
      "-m", mp,
      "-l", lang,
      "-f", "-",          // stdin
      "--no-timestamps",
      "--output-txt",
      "--stdout",
    ];

    console.log(`[Whisper] Starting: ${WHISPER_BIN} ${args.join(" ")}`);

    this.proc = spawn(WHISPER_BIN, args, {
      stdio: ["pipe", "pipe", "pipe"],
    });

    this.proc.stdout?.on("data", (chunk: Buffer) => {
      this.stdout += chunk.toString("utf-8");
    });

    this.proc.stderr?.on("data", (chunk: Buffer) => {
      console.error(`[Whisper] stderr: ${chunk.toString("utf-8")}`);
    });

    this.proc.on("error", (err) => {
      console.error(`[Whisper] Process error: ${err.message}`);
    });

    this.proc.on("exit", (code) => {
      console.log(`[Whisper] Process exited with code ${code}`);
      if (this.resolveStop) {
        this.resolveStop(this.stdout.trim());
        this.resolveStop = null;
      }
      this.proc = null;
    });

    return { ok: true, message: `Whisper started with model ${mdl}` };
  }

  /** Отправить аудио-чанк в stdin whisper-cli */
  writeAudio(chunk: Buffer): void {
    if (this.proc?.stdin?.writable) {
      this.proc.stdin.write(chunk);
    }
  }

  /** Получить текущий накопленный текст */
  getPartialText(): string {
    return this.stdout.trim();
  }

  /** Остановить whisper и получить финальный текст */
  async stop(): Promise<string> {
    if (!this.proc) {
      return "";
    }

    return new Promise<string>((resolve) => {
      this.resolveStop = resolve;
      // Закрываем stdin — whisper-cli завершит обработку и выйдет
      if (this.proc?.stdin) {
        this.proc.stdin.end();
      }

      // Таймаут 30 секунд на завершение
      setTimeout(() => {
        if (this.proc) {
          this.proc.kill("SIGTERM");
        }
        if (this.resolveStop) {
          this.resolveStop(this.stdout.trim());
          this.resolveStop = null;
        }
        this.proc = null;
      }, 30000);
    });
  }

  /** Уничтожить процесс (принудительно) */
  destroy(): void {
    if (this.proc) {
      this.proc.kill("SIGKILL");
      this.proc = null;
    }
    this.resolveStop = null;
  }
}

// Синглтон
export const whisperManager = new WhisperManager();
