import * as vscode from "vscode";
import { fetchInlineEditPatch } from "@termit/client";
import { buildEditorContext } from "./editorContext";
import { previewAndApplyPatch } from "./patchWorkflow";
import { getClient, getSessionId } from "./termitClient";

export async function runInlineEdit(context: vscode.ExtensionContext): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    void vscode.window.showWarningMessage("Open a file to use Termit inline edit.");
    return;
  }

  const block = buildEditorContext(editor);
  if (!block) {
    void vscode.window.showWarningMessage("File must be inside a workspace folder.");
    return;
  }

  const selectionText = editor.document.getText(editor.selection);
  if (!selectionText.trim()) {
    void vscode.window.showWarningMessage("Select code to edit, then run Termit inline edit.");
    return;
  }

  const instruction = await vscode.window.showInputBox({
    prompt: "Termit inline edit — describe the change",
    placeHolder: "Add error handling, rename vars, simplify…",
  });
  if (!instruction) {
    return;
  }

  const config = vscode.workspace.getConfiguration("termit");
  const model = config.get<string>("inlineEdit.model") || undefined;

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Termit inline edit",
      cancellable: false,
    },
    async () => {
      const client = getClient();
      const { patch } = await fetchInlineEditPatch(client, {
        instruction,
        filePath: block.relativePath,
        languageId: block.languageId,
        selectedText: selectionText,
        sessionId: getSessionId(context),
        model: model || undefined,
      });
      await previewAndApplyPatch(client, patch);
    }
  );
}
