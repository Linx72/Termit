import type { DesktopJourney } from "@termit/client";
import { journeyDescription, journeyTitle, type WorkflowTab } from "./northStar";
import { t, type Locale } from "./i18n";

interface WorkflowHubPanelProps {
  journeys: DesktopJourney[];
  activeJourneyId: string;
  locale: Locale;
  onSelectJourney: (journeyId: string) => void;
  onOpenTab: (tab: WorkflowTab) => void;
}

export function WorkflowHubPanel({
  journeys,
  activeJourneyId,
  locale,
  onSelectJourney,
  onOpenTab,
}: WorkflowHubPanelProps) {
  const active = journeys.find((item) => item.journey_id === activeJourneyId) ?? journeys[0];

  return (
    <div className="workflow-hub">
      <strong>{t(locale, "workflowHub")}</strong>
      <div className="chips workflow-journey-chips">
        {journeys.map((journey) => (
          <button
            key={journey.journey_id}
            type="button"
            className={`chip secondary compact ${activeJourneyId === journey.journey_id ? "active" : ""}`}
            onClick={() => {
              onSelectJourney(journey.journey_id);
              onOpenTab(journey.primary_tab as WorkflowTab);
            }}
          >
            {journeyTitle(journey, locale)}
          </button>
        ))}
      </div>
      {active ? (
        <>
          <p className="hint">{journeyDescription(active, locale)}</p>
          <ol className="workflow-steps">
            {active.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </>
      ) : null}
    </div>
  );
}
