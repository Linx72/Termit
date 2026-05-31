import * as vscode from "vscode";
import type { ApplyPatchRequest, ComposerFileContext, TaskType } from "@termit/client";
import {
  buildComposerMessage,
  parseComposerPatches,
  stripComposerJsonBlock,
  watchAgentRun,
} from "@termit/client";
import { applyAllComposerPatches, previewComposerPatch } from "./composerWorkflow";
import { appendContextToMessage, buildEditorContext } from "./editorContext";
import { previewAndApplyPatch } from "./patchWorkflow";
import { checkTermitHealth, getClient, getSessionId, setSessionId } from "./termitClient";
import { getSidebarHtml } from "./webviewContent";

type WebviewInbound =
  | { type: "init" }
  | { type: "chat"; message: string; taskType: TaskType; useRetrieval: boolean; model?: string }
  | { type: "task"; input: string; taskType: TaskType }
  | { type: "refreshTasks" }
  | { type: "getTask"; taskId: string }
  | { type: "refreshAgents" }
  | { type: "agentRun"; agentId: string; input: string }
  | { type: "addContext" }
  | { type: "clearSession" }
  | { type: "applyPatch"; request: ApplyPatchRequest }
  | { type: "composerAddFile" }
  | {
      type: "composerRun";
      instruction: string;
      model?: string;
      files: ComposerFileContext[];
    }
  | { type: "composerPreview"; index: number }
  | { type: "composerApplyAll" }
  | { type: "listAgentRuns"; agentId: string }
  | { type: "watchAgentRun"; runId: string }
  | { type: "stopAgentWatch" };

export class TermitSidebarProvider implements vscode.WebviewViewProvider, vscode.Disposable {
  public static readonly viewType = "termit.sidebar";

  private view?: vscode.WebviewView;
  private composerPatches: ApplyPatchRequest[] = [];
  private agentWatchAbort?: AbortController;

  constructor(private readonly context: vscode.ExtensionContext) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [],
    };

    const nonce = String(Date.now());
    webviewView.webview.html = getSidebarHtml(nonce);

    webviewView.webview.onDidReceiveMessage(async (message: WebviewInbound) => {
      await this.handleMessage(message);
    });
  }

  reveal(tab?: "chat" | "composer"): void {
    void vscode.commands.executeCommand("termit.sidebar.focus");
    if (tab) {
      this.postMessage({ type: "focusTab", tab });
    }
  }

  appendContextFromEditor(): void {
    const block = buildEditorContext(vscode.window.activeTextEditor);
    if (!block) {
      void vscode.window.showWarningMessage("Open a workspace file to attach context.");
      return;
    }
    this.postMessage({
      type: "contextAppended",
      text: `Context:\nFile: ${block.relativePath}\n${block.selection ? `Selection:\n\`\`\`\n${block.selection}\n\`\`\`` : ""}`,
    });
  }

  addComposerFileFromEditor(): void {
    const editor = vscode.window.activeTextEditor;
    const block = buildEditorContext(editor);
    if (!block || !editor) {
      void vscode.window.showWarningMessage("Open a workspace file to add to Composer.");
      return;
    }
    const content = editor.document.getText().slice(0, 12000);
    this.postMessage({
      type: "composerFileAdded",
      path: block.relativePath,
      content,
    });
  }

  private postMessage(message: Record<string, unknown>): void {
    void this.view?.webview.postMessage(message);
  }

  dispose(): void {
    this.stopAgentWatch();
  }

  private stopAgentWatch(): void {
    if (this.agentWatchAbort) {
      this.agentWatchAbort.abort();
      this.agentWatchAbort = undefined;
    }
  }

  private startAgentWatch(runId: string): void {
    this.stopAgentWatch();
    const client = getClient();
    const abort = new AbortController();
    this.agentWatchAbort = abort;

    void watchAgentRun(
      client,
      runId,
      ({ run, events }) => {
        this.postMessage({ type: "agentTimeline", run, events });
      },
      { signal: abort.signal, pollMs: 500, timeoutSeconds: 600 }
    ).catch((error) => {
      if (abort.signal.aborted) {
        return;
      }
      const detail = error instanceof Error ? error.message : String(error);
      this.postMessage({ type: "error", detail });
    });
  }

  private async handleMessage(message: WebviewInbound): Promise<void> {
    const client = getClient();

    try {
      if (message.type === "init") {
        const health = await checkTermitHealth(client);
        const providers = await client.listProviders();
        const models = providers.flatMap((item) => item.models);
        this.postMessage({ type: "status", text: `Termit · ${health}` });
        this.postMessage({ type: "models", models });
        return;
      }

      if (message.type === "clearSession") {
        const sessionId = `vscode_${Date.now().toString(36)}`;
        setSessionId(this.context, sessionId);
        this.postMessage({ type: "status", text: `New session: ${sessionId}` });
        return;
      }

      if (message.type === "addContext") {
        this.appendContextFromEditor();
        return;
      }

      if (message.type === "composerAddFile") {
        this.addComposerFileFromEditor();
        return;
      }

      if (message.type === "composerRun") {
        const payload = buildComposerMessage(message.instruction, message.files);
        let responseText = "";
        for await (const event of client.chatStream({
          message: payload,
          task_type: "coding",
          session_id: getSessionId(this.context),
          model: message.model || undefined,
          use_retrieval: true,
        })) {
          if (event.event === "meta") {
            const sessionId = String(event.data.session_id ?? "");
            if (sessionId) {
              setSessionId(this.context, sessionId);
            }
          } else if (event.event === "token") {
            const token = String(event.data.text ?? "");
            responseText += token;
            this.postMessage({ type: "composerToken", text: token });
          } else if (event.event === "error") {
            throw new Error(JSON.stringify(event.data));
          }
        }
        this.composerPatches = parseComposerPatches(responseText);
        this.postMessage({
          type: "composerDone",
          prose: stripComposerJsonBlock(responseText),
          patches: this.composerPatches,
        });
        return;
      }

      if (message.type === "composerPreview") {
        const patch = this.composerPatches[message.index];
        if (!patch) {
          throw new Error("Patch not found.");
        }
        await previewComposerPatch(patch);
        return;
      }

      if (message.type === "composerApplyAll") {
        const result = await applyAllComposerPatches(client, this.composerPatches);
        this.postMessage({ type: "composerApplyResult", applied: result.applied });
        return;
      }

      if (message.type === "chat") {
        const contextBlock = buildEditorContext(vscode.window.activeTextEditor);
        const config = vscode.workspace.getConfiguration("termit");
        const includeContext = config.get<boolean>("includeEditorContext", true);
        const fullMessage = includeContext
          ? appendContextToMessage(message.message, contextBlock)
          : message.message;

        for await (const event of client.chatStream({
          message: fullMessage,
          task_type: message.taskType,
          session_id: getSessionId(this.context),
          use_retrieval: message.useRetrieval,
          model: message.model || undefined,
        })) {
          if (event.event === "meta") {
            const sessionId = String(event.data.session_id ?? "");
            if (sessionId) {
              setSessionId(this.context, sessionId);
            }
            this.postMessage({ type: "meta", model: event.data.model });
          } else if (event.event === "token") {
            this.postMessage({ type: "token", text: String(event.data.text ?? "") });
          } else if (event.event === "done") {
            this.postMessage({ type: "done" });
          } else if (event.event === "error") {
            this.postMessage({ type: "error", detail: JSON.stringify(event.data) });
          }
        }
        return;
      }

      if (message.type === "task") {
        const task = await client.createTask({
          input: message.input,
          task_type: message.taskType,
          session_id: getSessionId(this.context),
        });
        this.postMessage({ type: "taskCreated", taskId: task.task_id });
        void vscode.window.showInformationMessage(`Termit task: ${task.task_id}`);
        return;
      }

      if (message.type === "refreshTasks") {
        const response = await client.listTasks(30);
        this.postMessage({ type: "tasks", tasks: response.tasks });
        return;
      }

      if (message.type === "getTask") {
        const task = await client.getTask(message.taskId);
        const detail = [
          `task_id: ${task.task_id}`,
          `state: ${task.state}`,
          `type: ${task.task_type}`,
          `updated: ${task.updated_at}`,
          task.error ? `error: ${task.error}` : "",
          task.report ? `report:\n${task.report}` : "",
        ]
          .filter(Boolean)
          .join("\n");
        this.postMessage({ type: "taskDetail", text: detail });
        return;
      }

      if (message.type === "refreshAgents") {
        const agents = await client.listAgents();
        this.postMessage({ type: "agents", agents });
        return;
      }

      if (message.type === "agentRun") {
        const run = await client.createAgentRun(message.agentId, {
          input: message.input,
          session_id: getSessionId(this.context),
        });
        this.postMessage({
          type: "agentRunCreated",
          runId: run.run_id,
          state: run.state,
        });
        this.startAgentWatch(run.run_id);
        void vscode.window.showInformationMessage(`Agent run queued: ${run.run_id}`);
        return;
      }

      if (message.type === "listAgentRuns") {
        const response = await client.listAgentRuns(message.agentId, 15);
        this.postMessage({ type: "agentRuns", runs: response.runs });
        return;
      }

      if (message.type === "watchAgentRun") {
        this.startAgentWatch(message.runId);
        return;
      }

      if (message.type === "stopAgentWatch") {
        this.stopAgentWatch();
        return;
      }

      if (message.type === "applyPatch") {
        await previewAndApplyPatch(client, message.request);
        return;
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      this.postMessage({ type: "error", detail });
      void vscode.window.showErrorMessage(`Termit: ${detail}`);
    }
  }
}

export async function createTaskFromSelection(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  const selection = editor?.document.getText(editor.selection).trim();
  const block = buildEditorContext(editor);
  const input =
    (block && selection ? appendContextToMessage(selection, block) : selection) ||
    (await vscode.window.showInputBox({ prompt: "Task input for Termit" }));
  if (!input) {
    return;
  }
  const config = vscode.workspace.getConfiguration("termit");
  const taskType = config.get<TaskType>("defaultTaskType", "coding");
  const task = await getClient().createTask({ input, task_type: taskType });
  void vscode.window.showInformationMessage(`Termit task created: ${task.task_id}`);
}
