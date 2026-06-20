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
  relax_env_warnings_enabled?: boolean;
  relaxed_env_warnings?: PlanStatusItem[];
  finetune_eval_kpi?: {
    kpi_passed?: boolean;
    delta?: number;
    reason?: string;
  } | null;
}

export interface ReloadDevMetricsSeedResult {
  reloaded: boolean;
  reason?: string;
  chat_requests_total?: number;
  chat_latency_p95_recent_ms?: number;
}

export async function getPlanStatus(client: TermitClient): Promise<PlanStatus> {
  return client.requestOps<PlanStatus>("/api/ops/plan-status");
}

/** Dev-only: перечитать data/desktop/dev_chat_metrics_seed.json в live telemetry. */
export async function reloadDevMetricsSeed(
  client: TermitClient,
): Promise<ReloadDevMetricsSeedResult> {
  return client.requestOps<ReloadDevMetricsSeedResult>("/api/ops/reload-dev-metrics-seed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
}
