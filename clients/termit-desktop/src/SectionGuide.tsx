import { t, type Locale, type MessageKey } from "./i18n";

export type SectionGuideKey =
  | "sidebar"
  | "chat"
  | "composer"
  | "editor"
  | "plan"
  | "terminal"
  | "tasks"
  | "agents"
  | "online"
  | "assignments"
  | "help";

const SECTION_META: Record<
  SectionGuideKey,
  { title: MessageKey; purpose: MessageKey; steps: MessageKey }
> = {
  sidebar: {
    title: "sgSidebarTitle",
    purpose: "sgSidebarPurpose",
    steps: "sgSidebarSteps",
  },
  chat: { title: "sgChatTitle", purpose: "sgChatPurpose", steps: "sgChatSteps" },
  composer: {
    title: "sgComposerTitle",
    purpose: "sgComposerPurpose",
    steps: "sgComposerSteps",
  },
  editor: { title: "sgEditorTitle", purpose: "sgEditorPurpose", steps: "sgEditorSteps" },
  plan: { title: "sgPlanTitle", purpose: "sgPlanPurpose", steps: "sgPlanSteps" },
  terminal: {
    title: "sgTerminalTitle",
    purpose: "sgTerminalPurpose",
    steps: "sgTerminalSteps",
  },
  tasks: { title: "sgTasksTitle", purpose: "sgTasksPurpose", steps: "sgTasksSteps" },
  agents: { title: "sgAgentsTitle", purpose: "sgAgentsPurpose", steps: "sgAgentsSteps" },
  online: { title: "sgOnlineTitle", purpose: "sgOnlinePurpose", steps: "sgOnlineSteps" },
  assignments: {
    title: "sgAssignmentsTitle",
    purpose: "sgAssignmentsPurpose",
    steps: "sgAssignmentsSteps",
  },
  help: { title: "sgHelpTitle", purpose: "sgHelpPurpose", steps: "sgHelpSteps" },
};

interface SectionGuideProps {
  locale: Locale;
  section: SectionGuideKey;
  className?: string;
}

export function SectionGuide({ locale, section, className = "" }: SectionGuideProps) {
  const meta = SECTION_META[section];
  const steps = t(locale, meta.steps)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <section className={`section-guide ${className}`.trim()} aria-label={t(locale, meta.title)}>
      <h4 className="section-guide-title">{t(locale, meta.title)}</h4>
      <p className="section-guide-purpose">{t(locale, meta.purpose)}</p>
      <p className="section-guide-how-label">{t(locale, "sectionGuideHowTo")}</p>
      <ol className="section-guide-steps">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </section>
  );
}
