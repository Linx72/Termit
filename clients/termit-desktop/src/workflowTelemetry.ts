import type { TermitClient } from "@termit/client";
import { recordDesktopWorkflowEvent } from "@termit/client";

export function trackWorkflowEvent(
  client: TermitClient,
  payload: {
    event_type: string;
    journey_id?: string;
    execution_mode?: string;
    duration_ms?: number;
    ok?: boolean;
    detail?: string;
  }
): void {
  void recordDesktopWorkflowEvent(client, payload).catch(() => {
    /* telemetry must not break UX */
  });
}
