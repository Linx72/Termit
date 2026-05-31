import * as vscode from "vscode";
import type { ApplyPatchRequest, TermitClient } from "@termit/client";
import { computePatchedContent } from "@termit/client";

export { computePatchedContent };

export async function previewAndApplyPatch(
  client: TermitClient,
  request: ApplyPatchRequest
): Promise<void> {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    throw new Error("Open a workspace folder before applying patches.");
  }

  const targetUri = vscode.Uri.joinPath(folder.uri, request.path);
  let current = "";
  let languageId = "plaintext";

  try {
    const document = await vscode.workspace.openTextDocument(targetUri);
    current = document.getText();
    languageId = document.languageId;
  } catch {
    if (!request.create && request.content === undefined) {
      throw new Error(`File not found: ${request.path}. Set create=true for new files.`);
    }
  }

  const patched = computePatchedContent(current, request);
  const previewDoc = await vscode.workspace.openTextDocument({
    content: patched,
    language: languageId,
  });

  const title = request.path;
  await vscode.commands.executeCommand(
    "vscode.diff",
    targetUri,
    previewDoc.uri,
    `${title} (Termit preview)`
  );

  const dryRun = await client.applyPatch({ ...request, dry_run: true, confirmed: false });
  if (dryRun.requires_confirmation) {
    vscode.window.showInformationMessage(
      `Patch preview ready (${dryRun.policy_reason ?? "confirmation required"})`
    );
  }

  const choice = await vscode.window.showWarningMessage(
    `Apply patch to ${request.path}?`,
    { modal: true },
    "Apply",
    "Cancel"
  );
  if (choice !== "Apply") {
    return;
  }

  const result = await client.applyPatch({ ...request, dry_run: false, confirmed: true });
  if (!result.applied) {
    throw new Error(result.policy_reason || "Patch was not applied.");
  }

  try {
    const updated = await vscode.workspace.openTextDocument(targetUri);
    await vscode.window.showTextDocument(updated, { preview: false });
  } catch {
    const created = await vscode.workspace.openTextDocument(targetUri);
    await vscode.window.showTextDocument(created);
  }

  vscode.window.showInformationMessage(
    `Patch applied to ${request.path} (${result.hunks_applied ?? 0} hunks)`
  );
}

export async function promptPatchFromUser(client: TermitClient): Promise<void> {
  const pathInput = await vscode.window.showInputBox({
    prompt: "Relative file path",
    placeHolder: "app/services/example.py",
  });
  if (!pathInput) {
    return;
  }

  const mode = await vscode.window.showQuickPick(
    ["Search/replace hunk", "Replace entire file"],
    { placeHolder: "Patch mode" }
  );
  if (!mode) {
    return;
  }

  if (mode === "Replace entire file") {
    const content = await vscode.window.showInputBox({
      prompt: "New file content (or paste in editor and copy)",
      placeHolder: "Leave empty to use active editor content",
    });
    const create =
      (await vscode.window.showQuickPick(["Update existing", "Create new"], {
        placeHolder: "File action",
      })) === "Create new";

    let finalContent = content ?? "";
    if (!finalContent) {
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        finalContent = editor.document.getText();
      }
    }

    await previewAndApplyPatch(client, {
      path: pathInput,
      content: finalContent,
      create,
    });
    return;
  }

  const oldText = await vscode.window.showInputBox({
    prompt: "old_text (must match exactly once)",
  });
  if (!oldText) {
    return;
  }
  const newText = await vscode.window.showInputBox({
    prompt: "new_text",
    value: "",
  });
  if (newText === undefined) {
    return;
  }

  await previewAndApplyPatch(client, {
    path: pathInput,
    hunks: [{ old_text: oldText, new_text: newText }],
  });
}

export function parsePatchFromClipboard(text: string): ApplyPatchRequest | undefined {
  try {
    const parsed = JSON.parse(text) as ApplyPatchRequest;
    if (typeof parsed.path !== "string") {
      return undefined;
    }
    if (!parsed.hunks && parsed.content === undefined) {
      return undefined;
    }
    return parsed;
  } catch {
    return undefined;
  }
}

export async function applyPatchFromClipboard(client: TermitClient): Promise<void> {
  const text = await vscode.env.clipboard.readText();
  const request = parsePatchFromClipboard(text);
  if (!request) {
    throw new Error("Clipboard does not contain valid apply_patch JSON.");
  }
  await previewAndApplyPatch(client, request);
}
