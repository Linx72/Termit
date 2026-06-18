import type { TermitClient } from "./client";

export interface PlanStatusItem {
  id: string;
  message: string;
}

export interface PlanStatus {
  phase: string;
  plan_code_complete: boolean;
  infra_ok: boolean;
  overall_ok: boolean;
  automatic_mode_enabled: boolean | null;
  blocker_count: number;
  warning_count: number;
  blockers: PlanStatusItem[];
  warnings: PlanStatusItem[];
  finetune_eval_kpi?: {
    kpi_passed?: boolean;
    delta?: number;
    reason?: string;
  } | null;
}

export async function getPlanStatus(client: TermitClient): Promise<PlanStatus> {
  return client.requestOps<PlanStatus>("/api/ops/plan-status");
}
