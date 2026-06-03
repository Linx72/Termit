import * as vscode from "vscode";
import { TermitClient } from "@termit/client";

export function getClient(): TermitClient {
  const config = vscode.workspace.getConfiguration("termit");
  const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  return new TermitClient({
    baseUrl: config.get<string>("baseUrl", "http://127.0.0.1:8765"),
    apiKey: config.get<string>("apiKey") || undefined,
    workspace: workspace || undefined,
  });
}

export function getSessionId(context: vscode.ExtensionContext): string | undefined {
  const config = vscode.workspace.getConfiguration("termit");
  const configured = config.get<string>("sessionId")?.trim();
  if (configured) {
    return configured;
  }
  let sessionId = context.globalState.get<string>("termit.sessionId");
  if (!sessionId) {
    sessionId = `vscode_${Date.now().toString(36)}`;
    void context.globalState.update("termit.sessionId", sessionId);
  }
  return sessionId;
}

export function setSessionId(context: vscode.ExtensionContext, sessionId: string): void {
  void context.globalState.update("termit.sessionId", sessionId);
}

export async function checkTermitHealth(client: TermitClient): Promise<string> {
  const statuses = await client.providersStatus();
  const okCount = statuses.filter((item) => item.ok).length;
  return `${okCount}/${statuses.length} providers OK`;
}
