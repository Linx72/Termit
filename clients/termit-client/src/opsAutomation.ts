import type { TermitClient } from "./client";

export interface AutomationToggleItem {
  toggle_id: string;
  env_key?: string | null;
  label_ru: string;
  label_en: string;
  description_ru: string;
  description_en: string;
  enabled: boolean;
  requires_restart?: boolean;
}

export interface AutomationPrefsResponse {
  env_path: string;
  automatic_mode_enabled: boolean;
  toggles: AutomationToggleItem[];
  schedulers: Record<string, unknown>;
  applied?: string[];
  restart_recommended?: boolean;
}

export interface AutomationPrefsUpdateRequest {
  toggles?: Record<string, boolean>;
  automatic_mode_enabled?: boolean;
}

export async function getAutomationPrefs(client: TermitClient): Promise<AutomationPrefsResponse> {
  return client.requestOps<AutomationPrefsResponse>("/api/ops/automation");
}

export async function updateAutomationPrefs(
  client: TermitClient,
  body: AutomationPrefsUpdateRequest,
): Promise<AutomationPrefsResponse> {
  return client.requestOps<AutomationPrefsResponse>("/api/ops/automation", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
