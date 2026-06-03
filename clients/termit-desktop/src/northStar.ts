import type { DesktopJourney } from "@termit/client";
import type { Locale } from "./i18n";

export type WorkflowTab = "chat" | "composer" | "editor" | "plan" | "terminal" | "tasks" | "agents" | "online";

export function journeyTitle(journey: DesktopJourney, locale: Locale): string {
  return locale === "ru" ? journey.title_ru : journey.title_en;
}

export function journeyDescription(journey: DesktopJourney, locale: Locale): string {
  return locale === "ru" ? journey.description_ru : journey.description_en;
}

export function tabForJourney(journey: DesktopJourney): WorkflowTab {
  const tab = journey.primary_tab;
  if (
    tab === "chat" ||
    tab === "composer" ||
    tab === "editor" ||
    tab === "plan" ||
    tab === "terminal" ||
    tab === "tasks" ||
    tab === "agents" ||
    tab === "online"
  ) {
    return tab;
  }
  return "chat";
}

export const DEFAULT_VERIFY_COMMANDS = [
  "python3 -m unittest discover -s tests -q",
  "git diff --stat",
];

export function parseCheckpointSummary(checkpointJson: string | null | undefined): string {
  if (!checkpointJson) {
    return "";
  }
  try {
    const payload = JSON.parse(checkpointJson) as Record<string, unknown>;
    const step = payload.step ?? "?";
    const pending = payload.pending_tool ? String(payload.pending_tool) : "none";
    return `checkpoint step ${String(step)} · pending ${pending}`;
  } catch {
    return "checkpoint available";
  }
}
