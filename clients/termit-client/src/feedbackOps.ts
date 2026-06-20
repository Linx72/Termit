import type { TermitClient } from "./client";

export interface FeedbackSummary {
  total: number;
  recent_7d: number;
  avg_rating: number | null;
  rating_counts: Record<string, number>;
}

export interface BetaMetrics {
  d30_retention_rate: number | null;
  cohort_size_d30: number;
  retained_d30: number;
  d7_retention_rate: number | null;
  cohort_size_d7: number;
  retained_d7: number;
  active_users_7d: number;
  tracked_actors: number;
  feedback_total: number;
  target_d30_retention: number;
}

export async function submitFeedback(
  client: TermitClient,
  body: {
    message: string;
    rating?: number;
    contact?: string;
    session_id?: string;
    task_id?: string;
    run_id?: string;
  },
): Promise<{ status: string; timestamp: string }> {
  return client.requestFeedback<{ status: string; timestamp: string }>("/api/feedback", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getFeedbackSummary(client: TermitClient): Promise<FeedbackSummary> {
  return client.requestFeedback<FeedbackSummary>("/api/feedback/summary");
}

export async function getBetaMetrics(client: TermitClient): Promise<BetaMetrics> {
  return client.requestOps<BetaMetrics>("/api/ops/beta-metrics");
}

export interface BetaActivityResult {
  recorded_at: string;
  session_id: string;
  tracked_actors: number;
  cohort_size_d30: number;
}

/** Heartbeat beta-сессии для cohort D30 (без rating). */
export async function recordBetaActivity(
  client: TermitClient,
  body: { session_id: string; source?: string },
): Promise<BetaActivityResult> {
  return client.requestOps<BetaActivityResult>("/api/ops/beta/activity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: body.session_id,
      source: body.source ?? "desktop",
    }),
  });
}
