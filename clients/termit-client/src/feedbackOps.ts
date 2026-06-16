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
