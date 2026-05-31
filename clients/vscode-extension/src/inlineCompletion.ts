import * as vscode from "vscode";
import { requestTabCompletion } from "@termit/client";
import { getClient } from "./termitClient";

export function registerInlineCompletion(context: vscode.ExtensionContext): void {
  const provider: vscode.InlineCompletionItemProvider = {
    async provideInlineCompletionItems(
      document: vscode.TextDocument,
      position: vscode.Position,
      _context: vscode.InlineCompletionContext,
      token: vscode.CancellationToken
    ) {
      const config = vscode.workspace.getConfiguration("termit");
      if (!config.get<boolean>("inlineCompletion.enabled", false)) {
        return undefined;
      }

      const minPrefix = config.get<number>("inlineCompletion.minPrefixLength", 12);
      const line = document.lineAt(position.line).text;
      const prefix = line.slice(0, position.character);
      if (prefix.trim().length < minPrefix) {
        return undefined;
      }

      const startLine = Math.max(0, position.line - 25);
      const endLine = Math.min(document.lineCount - 1, position.line + 8);
      const before = document.getText(
        new vscode.Range(startLine, 0, position.line, position.character)
      );
      const after = document.getText(
        new vscode.Range(position.line, position.character, endLine, document.lineAt(endLine).text.length)
      );

      if (token.isCancellationRequested) {
        return undefined;
      }

      try {
        const client = getClient();
        const model = config.get<string>("inlineCompletion.model") || undefined;
        const insertText = await requestTabCompletion(client, before, after, {
          model: model || undefined,
          task_type: "coding",
        });

        if (token.isCancellationRequested || !insertText) {
          return undefined;
        }

        const item = new vscode.InlineCompletionItem(insertText);
        item.range = new vscode.Range(position, position);
        return [item];
      } catch {
        return undefined;
      }
    },
  };

  context.subscriptions.push(
    vscode.languages.registerInlineCompletionItemProvider({ pattern: "**/*" }, provider)
  );
}
