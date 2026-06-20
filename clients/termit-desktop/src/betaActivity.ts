import type { TermitClient } from "@termit/client";
import { recordBetaActivity } from "@termit/client";
import { getOrCreateDeviceId } from "./onboardingExperiment";

const LAST_PING_KEY = "termit-beta-activity-last-ms";
const MIN_INTERVAL_MS = 24 * 60 * 60 * 1000;

/** Стабильный actor id для beta cohort (localStorage). */
export function getBetaActorId(): string {
  return getOrCreateDeviceId();
}

function shouldPingNow(): boolean {
  try {
    const raw = localStorage.getItem(LAST_PING_KEY);
    if (!raw) {
      return true;
    }
    const last = Number(raw);
    if (!Number.isFinite(last)) {
      return true;
    }
    return Date.now() - last >= MIN_INTERVAL_MS;
  } catch {
    return true;
  }
}

function markPinged(): void {
  try {
    localStorage.setItem(LAST_PING_KEY, String(Date.now()));
  } catch {
    // ignore quota errors
  }
}

/** Отправить beta heartbeat не чаще 1 раза в сутки. */
export async function recordBetaActivityIfDue(
  client: TermitClient,
  source = "desktop",
): Promise<boolean> {
  if (!shouldPingNow()) {
    return false;
  }
  await recordBetaActivity(client, {
    session_id: getBetaActorId(),
    source,
  });
  markPinged();
  return true;
}
