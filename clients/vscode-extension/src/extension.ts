import * as vscode from "vscode";
import { createCrossPlatformTaskFromPreset } from "./crossPlatformTask";
import { createTaskFromSelection, TermitSidebarProvider } from "./sidebarProvider";
import { applyPatchFromClipboard, promptPatchFromUser } from "./patchWorkflow";
import { runInlineEdit } from "./inlineEdit";
import { registerInlineCompletion } from "./inlineCompletion";
import { getClient } from "./termitClient";

export function activate(context: vscode.ExtensionContext): void {
  const provider = new TermitSidebarProvider(context);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(TermitSidebarProvider.viewType, provider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
    provider,
    vscode.commands.registerCommand("termit.openChat", () => {
      provider.reveal("chat");
    }),
    vscode.commands.registerCommand("termit.openComposer", () => {
      provider.reveal("composer");
    }),
    vscode.commands.registerCommand("termit.inlineEdit", () => {
      void runInlineEdit(context);
    }),
    vscode.commands.registerCommand("termit.createTask", () => {
      void createTaskFromSelection();
    }),
    vscode.commands.registerCommand("termit.crossPlatformTask", () => {
      void createCrossPlatformTaskFromPreset();
    }),
    vscode.commands.registerCommand("termit.addSelectionToChat", () => {
      provider.reveal("chat");
      provider.appendContextFromEditor();
    }),
    vscode.commands.registerCommand("termit.applyPatch", () => {
      void promptPatchFromUser(getClient());
    }),
    vscode.commands.registerCommand("termit.applyPatchFromClipboard", () => {
      void applyPatchFromClipboard(getClient()).catch((error: unknown) => {
        const detail = error instanceof Error ? error.message : String(error);
        void vscode.window.showErrorMessage(`Termit patch: ${detail}`);
      });
    }),
    vscode.commands.registerCommand("termit.refreshConnection", async () => {
      try {
        const health = await getClient().providersStatus();
        const ok = health.filter((item) => item.ok).length;
        void vscode.window.showInformationMessage(`Termit: ${ok}/${health.length} providers OK`);
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        void vscode.window.showErrorMessage(`Termit unreachable: ${detail}`);
      }
    })
  );

  registerInlineCompletion(context);
}

export function deactivate(): void {}
