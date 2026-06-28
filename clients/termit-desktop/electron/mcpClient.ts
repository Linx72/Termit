/**
 * MCP Client для TermitPro
 * 
 * Управляет запуском/остановкой MCP-серверов
 * и взаимодействием через JSON-RPC по stdio.
 * 
 * Поддерживаемые серверы:
 *   - Brave Search (brave_web_search, brave_local_search)
 */

import { spawn, ChildProcess } from 'node:child_process';
import { createInterface } from 'node:readline';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { app } from 'electron';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface MCPCallResult {
  content: Array<{ type: string; text: string }>;
  isError?: boolean;
}

interface JSONRPCMessage {
  jsonrpc: '2.0';
  id: string | number;
  method?: string;
  params?: unknown;
  result?: unknown;
  error?: { code: number; message: string };
}

export class MCPClient {
  private proc: ChildProcess | null = null;
  private pendingRequests = new Map<string | number, {
    resolve: (value: unknown) => void;
    reject: (reason: Error) => void;
  }>();
  private messageId = 0;
  private serverReady = false;
  private tools: MCPTool[] = [];
  private buffer = '';

  constructor(
    private readonly serverPath: string,
    private readonly serverName: string
  ) {}

  /**
   * Запустить MCP-сервер как subprocess
   */
  async start(env: Record<string, string> = {}): Promise<void> {
    if (this.proc) {
      console.error(`[MCP] ${this.serverName} уже запущен`);
      return;
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error(`[MCP] Таймаут запуска ${this.serverName} (10c)`));
      }, 10000);

      this.proc = spawn('node', [this.serverPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, ...env },
      });

      // Обработка stdout (JSON-RPC ответы)
      const rl = createInterface({ input: this.proc.stdout! });
      
      rl.on('line', (line: string) => {
        try {
          const msg = JSON.parse(line) as JSONRPCMessage;
          this.handleMessage(msg);
        } catch {
          // Игнорируем non-JSON строки (логи сервера)
        }
      });

      // stderr — логи сервера
      this.proc.stderr?.on('data', (data: Buffer) => {
        const text = data.toString().trim();
        if (text) console.error(`[MCP:${this.serverName}] ${text}`);
      });

      // Когда сервер готов (получили ответ на initialize)
      this.onceReady = () => {
        clearTimeout(timeout);
        this.serverReady = true;
        resolve();
      };

      // Обработка ошибок
      this.proc.on('error', (err) => {
        clearTimeout(timeout);
        reject(new Error(`[MCP] Ошибка запуска ${this.serverName}: ${err.message}`));
      });

      this.proc.on('exit', (code) => {
        clearTimeout(timeout);
        this.serverReady = false;
        this.proc = null;
        if (code !== 0) {
          console.error(`[MCP] ${this.serverName} завершился с кодом ${code}`);
        }
      });

      // Отправляем initialize
      this.sendRequest('initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: {
          name: 'termitpro',
          version: '0.3.6',
        },
      });
    });
  }

  private onceReady: (() => void) | null = null;

  /**
   * Список доступных инструментов
   */
  async listTools(): Promise<MCPTool[]> {
    if (!this.serverReady || !this.proc) {
      throw new Error(`[MCP] Сервер ${this.serverName} не запущен`);
    }

    const result = await this.sendRequest('tools/list') as { tools: MCPTool[] };
    this.tools = result.tools;
    return this.tools;
  }

  /**
   * Вызвать инструмент
   */
  async callTool(name: string, args: Record<string, unknown>): Promise<MCPCallResult> {
    if (!this.serverReady || !this.proc) {
      throw new Error(`[MCP] Сервер ${this.serverName} не запущен`);
    }

    const result = await this.sendRequest('tools/call', {
      name,
      arguments: args,
    }) as MCPCallResult;

    return result;
  }

  /**
   * Остановить MCP-сервер
   */
  async stop(): Promise<void> {
    if (this.proc) {
      this.proc.kill('SIGTERM');
      this.proc = null;
      this.serverReady = false;
      this.tools = [];
    }
  }

  /**
   * Статус сервера
   */
  getStatus(): { running: boolean; tools: string[]; serverName: string } {
    return {
      running: this.serverReady,
      tools: this.tools.map(t => t.name),
      serverName: this.serverName,
    };
  }

  /**
   * Отправить JSON-RPC запрос
   */
  private sendRequest(method: string, params?: unknown): Promise<unknown> {
    const id = ++this.messageId;
    const msg: JSONRPCMessage = {
      jsonrpc: '2.0',
      id,
      method,
      params,
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
      this.proc?.stdin?.write(JSON.stringify(msg) + '\n');
    });
  }

  /**
   * Обработка входящих JSON-RPC сообщений
   */
  private handleMessage(msg: JSONRPCMessage): void {
    if (msg.method === 'initialized' || (msg.id === 1 && msg.result !== undefined)) {
      // Сервер инициализирован
      if (this.onceReady) {
        this.onceReady();
        this.onceReady = null;
      }
      return;
    }

    if (msg.id !== undefined) {
      const pending = this.pendingRequests.get(msg.id);
      if (pending) {
        this.pendingRequests.delete(msg.id);
        if (msg.error) {
          pending.reject(new Error(msg.error.message));
        } else {
          pending.resolve(msg.result);
        }
      }
    }
  }
}

/**
 * Найти путь к MCP-серверу Brave Search
 */
function getBraveSearchServerPath(): string {
  // В production: собранный JS файл рядом с main.ts
  const prodPath = path.join(__dirname, '..', 'mcp-servers', 'brave-search', 'dist', 'index.js');
  
  // В dev: исходный TS файл
  const devPath = path.join(__dirname, '..', '..', 'mcp-servers', 'brave-search', 'src', 'index.ts');

  // Используем fs для проверки
  const fs = require('node:fs');
  if (fs.existsSync(prodPath)) return prodPath;
  if (fs.existsSync(devPath)) return devPath;
  
  // fallback
  return prodPath;
}

/**
 * Глобальный экземпляр MCP-клиента для Brave Search
 */
let braveSearchClient: MCPClient | null = null;

export function getBraveSearchClient(): MCPClient {
  if (!braveSearchClient) {
    const serverPath = getBraveSearchServerPath();
    braveSearchClient = new MCPClient(serverPath, 'brave-search');
  }
  return braveSearchClient;
}
