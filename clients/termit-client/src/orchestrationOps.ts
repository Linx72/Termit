import type { TermitClient } from "./client";

export interface BuildFromPlanRequest {
  plan_text: string;
  objective?: string;
  agent_id?: string;
  template_id?: string;
  session_id?: string;
  plan_run_id?: string;
  verify_after_patch?: boolean;
  priority?: number;
}

export interface BuildFromPlanResponse {
  run_id: string;
  agent_id: string;
  state: string;
  queued_position: number;
  input_preview: string;
}

export async function buildFromPlan(
  client: TermitClient,
  body: BuildFromPlanRequest,
): Promise<BuildFromPlanResponse> {
  return client.requestOrchestration<BuildFromPlanResponse>("/api/orchestration/build-from-plan", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
