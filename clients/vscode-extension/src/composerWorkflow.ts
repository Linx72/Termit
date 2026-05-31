import * as vscode from "vscode";
import type { ApplyPatchRequest, TermitClient } from "@termit/client";
import { computePatchedContent, previewAndApplyPatch } from "./patchWorkflow";

export async function previewComposerPatch(request: ApplyPatchRequest): Promise<void> {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    throw new Error("Open a workspace folder first.");
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
      throw new Error(`File not found: ${request.path}`);
    }
  }

  const patched = computePatchedContent(current, request);
  const previewDoc = await vscode.workspace.openTextDocument({
    content: patched,
    language: languageId,
  });

  await vscode.commands.executeCommand(
    "vscode.diff",
    targetUri,
    previewDoc.uri,
    `${request.path} (Composer preview)`
  );
}

export async function applyAllComposerPatches(
  client: TermitClient,
  patches: ApplyPatchRequest[]
): Promise<{ applied: number; errors: string[] }> {
  if (patches.length === 0) {
    return { applied: 0, errors: [] };
  }

  const choice = await vscode.window.showWarningMessage(
    `Apply ${patches.length} file patch(es) from Composer?`,
    { modal: true },
    "Apply all",
    "Cancel"
  );
  if (choice !== "Apply all") {
    return { applied: 0, errors: [] };
  }

  let applied = 0;
  const errors: string[] = [];
  for (const patch of patches) {
    try {
      const result = await client.applyPatch({ ...patch, confirmed: true, dry_run: false });
      if (!result.applied) {
        errors.push(`${patch.path}: ${result.policy_reason ?? "not applied"}`);
        continue;
      }
      applied += 1;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`${patch.path}: ${message}`);
    }
  }

  if (applied > 0) {
    void vscode.window.showInformationMessage(`Composer applied ${applied}/${patches.length} patch(es).`);
  }
  if (errors.length > 0) {
    void vscode.window.showErrorMessage(errors.slice(0, 3).join("\n"));
  }
  return { applied, errors };
}
