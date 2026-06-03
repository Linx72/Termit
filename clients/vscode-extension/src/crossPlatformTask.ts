import * as vscode from "vscode";
import { launchCrossPlatformPreset, CROSS_PLATFORM_PRESETS } from "@termit/client";
import { getClient } from "./termitClient";

export async function createCrossPlatformTaskFromPreset(): Promise<void> {
  const config = vscode.workspace.getConfiguration("termit");
  const workspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  const items = CROSS_PLATFORM_PRESETS.map((preset) => ({
    label: preset.labelEn,
    description: preset.goal.slice(0, 120),
    preset,
  }));

  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: "Cross-platform app or game (iOS / macOS / Windows / Android)",
  });
  if (!picked) {
    return;
  }

  const client = getClient();
  if (workspace) {
    (client as { workspace?: string }).workspace = workspace;
  }

  const mode = await vscode.window.showQuickPick(
    [
      { label: "Draft first step", value: "draft" as const },
      { label: "Run full atomic workflow (agent)", value: "run" as const },
    ],
    { placeHolder: "Mode" }
  );
  if (!mode) {
    return;
  }

  if (mode.value === "draft") {
    const { buildPresetDraft } = await import("@termit/client");
    const input = await buildPresetDraft(client, picked.preset);
    const task = await client.createTask({ input, task_type: "coding" });
    void vscode.window.showInformationMessage(`Termit task ${task.task_id}`);
    return;
  }

  void vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: `Termit atomic: ${picked.preset.labelEn}`,
      cancellable: false,
    },
    async () => {
      const result = await launchCrossPlatformPreset(client, picked.preset, {
        stopOnVerifyFailure: true,
      });
      const summary = result.aborted
        ? `Stopped after ${result.steps.length} steps (verify failed)`
        : `Completed ${result.steps.length} atomic steps`;
      void vscode.window.showInformationMessage(`Termit: ${summary}`);
    }
  );
}
