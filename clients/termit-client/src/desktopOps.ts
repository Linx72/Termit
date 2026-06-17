import type { TermitClient } from "./client";

export interface DesktopJourney {
  journey_id: string;
  title_ru: string;
  title_en: string;
  description_ru: string;
  description_en: string;
  modes: string[];
  steps: string[];
  primary_tab: string;
}

export interface DesktopNorthStarResponse {
  journeys: DesktopJourney[];
  kpi_targets: Record<string, number>;
}

export interface DesktopKpiGateItem {
  gate_id: string;
  label: string;
  actual: number;
  target: number;
  passed: boolean;
  higher_is_better: boolean;
}

export interface DesktopKpiGateResponse {
  overall_passed: boolean;
  passed_count: number;
  total_gates: number;
  gates: DesktopKpiGateItem[];
  targets: Record<string, number>;
  journeys: DesktopJourney[];
}

export interface AgentPolicyPreset {
  preset_id: string;
  name: string;
  description_ru: string;
  description_en: string;
  max_tool_steps: number;
  allow_online: boolean;
  auto_confirm_risky_tools: boolean;
  verify_after_patch: boolean;
  enabled_tools: string[];
  execution_mode: string;
}

export interface DesktopSharedRun {
  share_id: string;
  run_id: string;
  team: string;
  note: string;
  shared_by: string;
  shared_at: string;
  snapshot: Record<string, unknown>;
}

export interface DesktopHeavyJob {
  job_id: string;
  job_type: string;
  state: string;
  payload: Record<string, unknown>;
  requested_by: string;
  created_at: string;
  updated_at: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
}

export async function listDesktopJourneys(client: TermitClient): Promise<DesktopNorthStarResponse> {
  return client.requestDesktop<DesktopNorthStarResponse>("/api/desktop/journeys");
}

export async function getDesktopKpiGates(client: TermitClient): Promise<DesktopKpiGateResponse> {
  return client.requestDesktop<DesktopKpiGateResponse>("/api/desktop/kpi-gates");
}

export async function listPolicyPresets(client: TermitClient): Promise<AgentPolicyPreset[]> {
  return client.requestDesktop<AgentPolicyPreset[]>("/api/desktop/policy-presets");
}

export async function listSharedRuns(
  client: TermitClient,
  options: { limit?: number; team?: string } = {}
): Promise<{ shared_runs: DesktopSharedRun[]; total: number }> {
  const query = new URLSearchParams();
  if (options.limit != null) {
    query.set("limit", String(options.limit));
  }
  if (options.team) {
    query.set("team", options.team);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return client.requestDesktop(`/api/desktop/shared-runs${suffix}`);
}

export async function shareAgentRun(
  client: TermitClient,
  payload: { run_id: string; team?: string; note?: string; shared_by?: string }
): Promise<DesktopSharedRun> {
  return client.requestDesktop<DesktopSharedRun>("/api/desktop/shared-runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listHeavyJobs(
  client: TermitClient,
  limit = 20
): Promise<{ jobs: DesktopHeavyJob[]; total: number }> {
  return client.requestDesktop(`/api/desktop/heavy-jobs?limit=${limit}`);
}

export async function enqueueHeavyJob(
  client: TermitClient,
  payload: { job_type: string; payload?: Record<string, unknown>; requested_by?: string }
): Promise<DesktopHeavyJob> {
  return client.requestDesktop<DesktopHeavyJob>("/api/desktop/heavy-jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getHeavyJob(client: TermitClient, jobId: string): Promise<DesktopHeavyJob> {
  return client.requestDesktop<DesktopHeavyJob>(`/api/desktop/heavy-jobs/${encodeURIComponent(jobId)}`);
}

export async function recordDesktopWorkflowEvent(
  client: TermitClient,
  payload: {
    event_type: string;
    journey_id?: string;
    execution_mode?: string;
    duration_ms?: number;
    ok?: boolean;
    detail?: string;
    metadata?: Record<string, unknown>;
  }
): Promise<{ event_id: string; event_type: string; timestamp: string }> {
  return client.requestDesktop("/api/desktop/workflow-events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface OnboardingVariantMetrics {
  variant: string;
  assigned: number;
  completed: number;
  conversion_rate: number | null;
  median_completion_ms: number | null;
}

export interface OnboardingMetricsResponse {
  total_assigned: number;
  total_completed: number;
  overall_conversion_rate: number | null;
  variants: OnboardingVariantMetrics[];
  unknown_assigned: number;
  unknown_completed: number;
}

export async function getOnboardingMetrics(client: TermitClient): Promise<OnboardingMetricsResponse> {
  return client.requestDesktop<OnboardingMetricsResponse>("/api/desktop/onboarding-metrics");
}
