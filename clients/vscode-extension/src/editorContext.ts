import * as path from "node:path";
import * as vscode from "vscode";

export interface EditorContextBlock {
  relativePath: string;
  languageId: string;
  selection?: string;
  excerpt?: string;
}

export function getWorkspaceRelativePath(document: vscode.TextDocument): string | undefined {
  const folder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!folder) {
    return undefined;
  }
  return path.relative(folder.uri.fsPath, document.uri.fsPath).replace(/\\/g, "/");
}

export function buildEditorContext(editor?: vscode.TextEditor): EditorContextBlock | undefined {
  if (!editor) {
    return undefined;
  }
  const relativePath = getWorkspaceRelativePath(editor.document);
  if (!relativePath) {
    return undefined;
  }

  const selection = editor.selection;
  const selectedText = editor.document.getText(selection).trim();
  let excerpt: string | undefined;
  if (!selectedText && !selection.isEmpty) {
    excerpt = editor.document.getText(selection);
  } else if (!selectedText) {
    const line = selection.active.line;
    const start = Math.max(0, line - 20);
    const end = Math.min(editor.document.lineCount - 1, line + 20);
    excerpt = editor.document.getText(new vscode.Range(start, 0, end + 1, 0));
  }

  return {
    relativePath,
    languageId: editor.document.languageId,
    selection: selectedText || undefined,
    excerpt: selectedText ? undefined : excerpt,
  };
}

export function formatContextForPrompt(block: EditorContextBlock): string {
  const parts = [`File: ${block.relativePath}`, `Language: ${block.languageId}`];
  if (block.selection) {
    parts.push("Selection:", "```", block.selection, "```");
  } else if (block.excerpt) {
    parts.push("Excerpt:", "```", block.excerpt.slice(0, 4000), "```");
  }
  return parts.join("\n");
}

export function appendContextToMessage(message: string, block?: EditorContextBlock): string {
  if (!block) {
    return message;
  }
  return `${message.trim()}\n\n---\nContext:\n${formatContextForPrompt(block)}`;
}
